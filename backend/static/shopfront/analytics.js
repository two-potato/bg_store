(function () {
  var firedKeys = new Set();
  var consentState = null;
  var providersReady = false;
  var posthogLoaded = false;
  var clarityLoaded = false;
  var posthogBooting = false;
  var clarityBooting = false;
  var pageviewKey = "";

  function readJsonScript(id, fallback) {
    var node = document.getElementById(id);
    if (!node) return fallback;
    try {
      return JSON.parse(node.textContent || "");
    } catch (_) {
      return fallback;
    }
  }

  var runtimeConfig = readJsonScript("servio-analytics-config", {}) || {};
  var identity = readJsonScript("servio-analytics-identity", {}) || {};
  var requireConsent = readJsonScript("servio-analytics-consent-mode", true);

  function hasValue(value) {
    return typeof value === "string" ? value.trim() !== "" : !!value;
  }

  function sanitizeEventProperties(payload) {
    var cloned = Object.assign({}, payload);
    delete cloned.event;
    delete cloned.ecommerce;
    delete cloned.page_location;
    delete cloned.page_path;
    delete cloned.page_title;
    delete cloned.user;
    delete cloned.email;
    delete cloned.phone;
    delete cloned.name;
    delete cloned.first_name;
    delete cloned.last_name;
    return cloned;
  }

  function getConsentState() {
    if (consentState) return consentState;
    if (window.ServioConsent && typeof window.ServioConsent.get === "function") {
      consentState = window.ServioConsent.get();
      return consentState;
    }
    try {
      consentState = localStorage.getItem("cookie_consent") || "";
    } catch (_) {
      consentState = "";
    }
    return consentState;
  }

  function analyticsAllowed() {
    if (requireConsent === false || runtimeConfig.require_consent === false) return true;
    return getConsentState() === "accepted";
  }

  function stableKey(payload) {
    if (!payload || typeof payload !== "object") return "";
    if (payload.event === "product_view") {
      return "product_view:" + ((((payload.ecommerce || {}).items || [])[0] || {}).item_id || "");
    }
    if (payload.event === "begin_checkout") {
      return "begin_checkout:" + ((((payload.ecommerce || {}).items || []).length) || 0);
    }
    if (payload.event === "checkout_step_view") {
      return "checkout_step_view:" + (payload.checkout_step || "") + ":" + window.location.pathname;
    }
    if (payload.event === "checkout_error") {
      return "checkout_error:" + (payload.checkout_step || "") + ":" + (payload.error_message || "");
    }
    if (payload.event === "payment_started") {
      return "payment_started:" + (payload.order_id || "");
    }
    if (payload.event === "payment_failed") {
      return "payment_failed:" + (payload.order_id || "") + ":" + (payload.payment_event || "");
    }
    if (payload.event === "purchase") {
      return "purchase:" + (((payload.ecommerce || {}).transaction_id) || "");
    }
    return "";
  }

  function enrich(payload) {
    var authenticated = !!identity.is_authenticated;
    return Object.assign(
      {
        page_location: window.location.href,
        page_path: window.location.pathname,
        page_title: document.title,
        page_type: runtimeConfig.page_type || "page",
        site_vertical: runtimeConfig.site_vertical || "marketplace",
        platform: runtimeConfig.platform || "web",
        currency: runtimeConfig.currency || "RUB",
        user_state: authenticated ? "authenticated" : "anonymous",
        auth_state: authenticated ? "authenticated" : "anonymous",
      },
      payload
    );
  }

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      script.async = true;
      script.src = src;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  function normalizePosthogHost(host) {
    var value = (host || "https://app.posthog.com").replace(/\/+$/, "");
    return value;
  }

  function posthogAssetUrl(host) {
    var normalized = normalizePosthogHost(host);
    return normalized.replace(".i.posthog.com", "-assets.i.posthog.com") + "/static/array.js";
  }

  function ensurePosthog() {
    if (posthogLoaded || !hasValue(runtimeConfig.posthog_api_key) || posthogBooting) {
      return Promise.resolve();
    }
    posthogBooting = true;
    window.posthog = window.posthog || [];
    window.posthog._i = window.posthog._i || [];
    window.posthog.__SV = 1;

    function stub(method) {
      window.posthog[method] = function () {
        window.posthog.push([method].concat(Array.prototype.slice.call(arguments, 0)));
      };
    }

    var methods = [
      "init",
      "capture",
      "identify",
      "reset",
      "set_config",
      "register",
      "register_once",
      "unregister",
      "opt_in_capturing",
      "opt_out_capturing",
      "has_opted_out_capturing",
      "setPersonProperties",
    ];
    methods.forEach(stub);

    return loadScript(posthogAssetUrl(runtimeConfig.posthog_host))
      .then(function () {
        window.posthog.init(runtimeConfig.posthog_api_key, {
          api_host: normalizePosthogHost(runtimeConfig.posthog_host),
          defaults: "2026-01-30",
          autocapture: true,
          capture_pageview: false,
          capture_pageleave: true,
          persistence: "localStorage+cookie",
          person_profiles: "identified_only",
          session_recording: {
            maskAllInputs: true,
            maskInputOptions: {
              password: true,
              email: true,
              tel: true,
            },
          },
          before_send: function (event) {
            if (!event || !event.event) return event;
            if (String(window.location.pathname || "").indexOf("/admin/") === 0) return null;
            return event;
          },
          loaded: function (instance) {
            instance.register({
              site_vertical: runtimeConfig.site_vertical || "marketplace",
              platform: runtimeConfig.platform || "web",
              currency: runtimeConfig.currency || "RUB",
            });
          },
        });
        posthogLoaded = true;
      })
      .catch(function () {})
      .finally(function () {
        posthogBooting = false;
      });
  }

  function ensureClarity() {
    if (clarityLoaded || !hasValue(runtimeConfig.clarity_project_id) || clarityBooting) {
      return Promise.resolve();
    }
    clarityBooting = true;
    window.clarity =
      window.clarity ||
      function () {
        (window.clarity.q = window.clarity.q || []).push(arguments);
      };

    return loadScript("https://www.clarity.ms/tag/" + encodeURIComponent(runtimeConfig.clarity_project_id))
      .then(function () {
        clarityLoaded = true;
      })
      .catch(function () {})
      .finally(function () {
        clarityBooting = false;
      });
  }

  function applyIdentity() {
    if (!identity || !identity.is_authenticated) {
      try {
        var previousDistinctId = localStorage.getItem("servio.analytics.distinct_id");
        if (previousDistinctId && window.posthog && typeof window.posthog.reset === "function") {
          window.posthog.reset();
        }
        localStorage.removeItem("servio.analytics.distinct_id");
      } catch (_) {}
      return;
    }

    try {
      localStorage.setItem("servio.analytics.distinct_id", identity.distinct_id || "");
    } catch (_) {}

    if (window.posthog && typeof window.posthog.identify === "function" && identity.distinct_id) {
      try {
        window.posthog.identify(identity.distinct_id, identity.properties || {});
      } catch (_) {}
    }

    if (typeof window.clarity === "function" && identity.clarity_custom_id) {
      try {
        window.clarity(
          "identify",
          identity.clarity_custom_id,
          identity.clarity_session_id || "",
          identity.clarity_page_id || "",
          identity.clarity_friendly_name || ""
        );
      } catch (_) {}
      try {
        window.clarity("set", "role", ((identity.properties || {}).role || "buyer"));
        window.clarity("set", "user_state", "authenticated");
      } catch (_) {}
    }
  }

  function ensureProvidersForConsent() {
    if (!analyticsAllowed()) {
      if (window.posthog && typeof window.posthog.opt_out_capturing === "function") {
        try {
          window.posthog.opt_out_capturing();
        } catch (_) {}
      }
      if (typeof window.clarity === "function") {
        try {
          window.clarity("consentv2", {
            ad_Storage: "denied",
            analytics_Storage: "denied",
          });
        } catch (_) {}
      }
      providersReady = false;
      return Promise.resolve(false);
    }

    return Promise.all([ensurePosthog(), ensureClarity()]).then(function () {
      providersReady = true;
      if (window.posthog && typeof window.posthog.opt_in_capturing === "function") {
        try {
          window.posthog.opt_in_capturing();
        } catch (_) {}
      }
      if (typeof window.clarity === "function") {
        try {
          window.clarity("consentv2", {
            ad_Storage: "granted",
            analytics_Storage: "granted",
          });
        } catch (_) {}
      }
      applyIdentity();
      pageviewKey = "";
      trackPageView("page_view");
      return true;
    });
  }

  function push(payload) {
    if (!payload || typeof payload !== "object" || !payload.event) return;
    var key = stableKey(payload);
    if (key && firedKeys.has(key)) return;
    if (key) firedKeys.add(key);

    var enriched = enrich(payload);

    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push(enriched);

    if (analyticsAllowed() && window.posthog && typeof window.posthog.capture === "function") {
      try {
        window.posthog.capture(enriched.event, sanitizeEventProperties(enriched));
      } catch (_) {}
    }

    if (analyticsAllowed() && typeof window.clarity === "function") {
      try {
        window.clarity("event", enriched.event);
      } catch (_) {}
    }

    try {
      document.body.dispatchEvent(new CustomEvent("servio:analytics-pushed", { detail: enriched }));
    } catch (_) {}
  }

  function hydrate(root) {
    var scope = root || document;
    var nodes = scope.querySelectorAll
      ? scope.querySelectorAll('script[data-analytics-payload]:not([data-analytics-fired="1"])')
      : [];
    nodes.forEach(function (node) {
      node.setAttribute("data-analytics-fired", "1");
      try {
        push(JSON.parse(node.textContent || "{}"));
      } catch (_) {}
    });
  }

  function trackPageView(eventName) {
    var key = [window.location.pathname, window.location.search, document.title].join("|");
    if (pageviewKey === key) return;
    pageviewKey = key;
    push({
      event: eventName || "page_view",
      page_type: runtimeConfig.page_type || "page",
    });
  }

  function handleConsentChange(nextState) {
    consentState = nextState || "";
    ensureProvidersForConsent();
  }

  document.addEventListener("DOMContentLoaded", function () {
    ensureProvidersForConsent().then(function () {
      hydrate(document);
      if (!providersReady) {
        trackPageView("page_view");
      }
    });
  });

  document.body.addEventListener("htmx:load", function (e) {
    hydrate((e.detail && e.detail.elt) || document);
  });

  document.body.addEventListener("htmx:afterSettle", function () {
    pageviewKey = "";
    trackPageView("page_view");
  });

  document.body.addEventListener("analyticsEvent", function (e) {
    push((e && e.detail) || {});
  });

  document.addEventListener("servio:cookie-consent-changed", function (e) {
    handleConsentChange((e.detail && e.detail.value) || "");
  });

  document.body.addEventListener("click", function (e) {
    var target = e.target && e.target.closest ? e.target.closest("[data-search-click]") : null;
    if (!target) return;
    push({
      event: "search_result_click",
      search_term: target.getAttribute("data-search-query") || "",
      search_origin: target.getAttribute("data-search-origin") || "catalog_grid",
      item_id: target.getAttribute("data-search-product-id") || "",
      item_name: target.getAttribute("data-search-product-name") || "",
      position: parseInt(target.getAttribute("data-search-position") || "0", 10) || 0,
    });
  });

  document.body.addEventListener("click", function (e) {
    var target = e.target && e.target.closest ? e.target.closest("[data-recommendation-click]") : null;
    if (!target) return;
    push({
      event: "recommendation_click",
      recommendation_source: target.getAttribute("data-recommendation-source") || "",
      item_id: target.getAttribute("data-search-product-id") || "",
      item_name: target.getAttribute("data-search-product-name") || "",
      position: parseInt(target.getAttribute("data-search-position") || "0", 10) || 0,
    });
  });

  window.ServioAnalytics = {
    push: push,
    hydrate: hydrate,
    initProviders: ensureProvidersForConsent,
    trackPageView: trackPageView,
  };
})();
