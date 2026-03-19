(function () {
  function readJsonScript(id, fallback) {
    var node = document.getElementById(id);
    if (!node) return fallback;
    try {
      return JSON.parse(node.textContent || "");
    } catch (_) {
      return fallback;
    }
  }

  function hasValue(value) {
    return typeof value === "string" ? value.trim() !== "" : !!value;
  }

  function normalizeText(value) {
    return String(value || "").toLowerCase();
  }

  function containsIgnoredPattern(value) {
    var text = normalizeText(value);
    if (!text) return false;
    return [
      "telegramnetworkerror",
      "serverdisconnectederror",
      "servio frontend smoke test",
    ].some(function (pattern) {
      return text.indexOf(pattern) >= 0;
    });
  }

  function currentState() {
    if (window.ServioRuntime && typeof window.ServioRuntime.current === "function") {
      return window.ServioRuntime.current();
    }
    return {
      path: window.location.pathname || "/",
      pageTypes: [document.body && document.body.getAttribute("data-page-type") || "page"],
    };
  }

  function targetSummary(target) {
    if (!target || !target.tagName) return "";
    var attrs = [];
    if (target.id) attrs.push("#" + target.id);
    if (target.className && typeof target.className === "string") {
      attrs.push("." + target.className.trim().split(/\s+/).slice(0, 3).join("."));
    }
    return String(target.tagName).toLowerCase() + attrs.join("");
  }

  var config = readJsonScript("servio-monitoring-config", {}) || {};
  var identity = readJsonScript("servio-analytics-identity", {}) || {};
  var sentry = window.Sentry;
  var initialized = false;

  function scopeExtras(extra) {
    var state = currentState();
    return Object.assign(
      {
        page_path: state.path || window.location.pathname || "/",
        page_types: state.pageTypes || [],
        page_title: document.title || "",
      },
      extra || {}
    );
  }

  function withScope(callback, extra) {
    if (!sentry || !initialized) return;
    sentry.withScope(function (scope) {
      var extras = scopeExtras(extra);
      Object.keys(extras).forEach(function (key) {
        scope.setExtra(key, extras[key]);
      });
      callback(scope);
    });
  }

  function configureScope(callback) {
    if (!sentry || typeof sentry.configureScope !== "function") return;
    sentry.configureScope(callback);
  }

  function captureMessage(message, level, extra) {
    if (!sentry || !initialized || !hasValue(message) || containsIgnoredPattern(message)) return;
    withScope(function () {
      sentry.captureMessage(message, level || "error");
    }, extra);
  }

  function captureException(error, extra) {
    if (!sentry || !initialized || !error) return;
    var message = "";
    if (typeof error === "string") {
      message = error;
    } else if (error && typeof error.message === "string") {
      message = error.message;
    }
    if (containsIgnoredPattern(message)) return;
    withScope(function () {
      sentry.captureException(error);
    }, extra);
  }

  function initSentry() {
    if (initialized || !sentry || !hasValue(config.sentry_dsn)) return false;
    sentry.init({
      dsn: config.sentry_dsn,
      environment: config.sentry_environment || "development",
      release: config.sentry_release || undefined,
      sendDefaultPii: false,
      autoSessionTracking: false,
      attachStacktrace: true,
      maxBreadcrumbs: 50,
      tracesSampleRate: 0,
      beforeSend: function (event) {
        if (!event) return event;
        if (String(window.location.pathname || "").indexOf("/admin/") === 0) return null;
        var candidates = [];
        if (event.message) candidates.push(event.message);
        if (event.logentry && event.logentry.formatted) candidates.push(event.logentry.formatted);
        (((event.exception || {}).values) || []).forEach(function (value) {
          if (value && value.value) candidates.push(value.value);
          if (value && value.type) candidates.push(value.type);
        });
        if (candidates.some(containsIgnoredPattern)) return null;
        event.tags = Object.assign({}, event.tags, {
          page_type: config.page_type || (document.body && document.body.getAttribute("data-page-type")) || "page",
          platform: "web",
        });
        return event;
      },
    });
    configureScope(function (scope) {
      if (!scope) return;
      if (identity && identity.is_authenticated) {
        scope.setUser({
          id: (identity.properties || {}).user_id || identity.distinct_id || "",
          username: (identity.properties || {}).username || "",
        });
        scope.setTag("user_state", "authenticated");
        if ((identity.properties || {}).role) {
          scope.setTag("user_role", identity.properties.role);
        }
        return;
      }
      scope.setTag("user_state", "anonymous");
    });
    initialized = true;
    return true;
  }

  function bindMonitoring() {
    if (!initialized || !document.body) return;

    window.addEventListener("error", function (event) {
      if (!event || !event.target || event.target === window || !event.target.tagName) return;
      captureMessage("resource_load_error", "error", {
        kind: "resource",
        tag_name: String(event.target.tagName).toLowerCase(),
        target: targetSummary(event.target),
        source_url: event.target.currentSrc || event.target.src || event.target.href || "",
      });
    }, true);

    document.addEventListener("securitypolicyviolation", function (event) {
      captureMessage("csp_violation", "error", {
        kind: "csp",
        blocked_uri: event.blockedURI || "",
        violated_directive: event.violatedDirective || "",
        effective_directive: event.effectiveDirective || "",
        original_policy: event.originalPolicy || "",
        source_file: event.sourceFile || "",
        line_number: event.lineNumber || 0,
        column_number: event.columnNumber || 0,
      });
    });

    [
      "htmx:responseError",
      "htmx:sendError",
      "htmx:swapError",
      "htmx:targetError"
    ].forEach(function (eventName) {
      document.body.addEventListener(eventName, function (event) {
        var detail = event && event.detail ? event.detail : {};
        var xhr = detail.xhr || {};
        var requestConfig = detail.requestConfig || {};
        captureMessage(eventName, "error", {
          kind: "htmx",
          event_name: eventName,
          target: targetSummary(detail.elt || requestConfig.elt || event.target),
          request_path: requestConfig.path || requestConfig.url || "",
          verb: requestConfig.verb || "",
          status: xhr.status || 0,
          response_text: typeof xhr.responseText === "string" ? xhr.responseText.slice(0, 500) : "",
        });
      });
    });
  }

  initSentry();
  bindMonitoring();

  window.ServioMonitoring = {
    captureMessage: captureMessage,
    captureException: captureException,
    isReady: function () {
      return !!initialized;
    },
  };
})();
