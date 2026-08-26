(function () {
  function monitoring() {
    return window.ServioMonitoring || null;
  }

  function runtime() {
    return window.ServioRuntime || null;
  }

  function showToast(message, variant) {
    var rt = runtime();
    if (rt && typeof rt.showToast === "function") {
      rt.showToast(message, variant || "warning");
      return;
    }
    if (window.ShopToast && typeof window.ShopToast.show === "function") {
      window.ShopToast.show({ message: message, variant: variant || "warning" });
    }
  }

  function csrfToken() {
    var rt = runtime();
    if (!rt || typeof rt.getCookie !== "function") return "";
    return rt.getCookie("csrftoken");
  }

  function defaultLoginUrl() {
    return "/account/login/?next=" + encodeURIComponent(window.location.pathname + window.location.search);
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function captureSocialError(message, extra, error) {
    var monitor = monitoring();
    if (!monitor) return;
    if (error && typeof monitor.captureException === "function") {
      monitor.captureException(error, Object.assign({ kind: "social_toggle" }, extra || {}));
      return;
    }
    if (typeof monitor.captureMessage === "function") {
      monitor.captureMessage(message, "error", Object.assign({ kind: "social_toggle" }, extra || {}));
    }
  }

  function parseJsonResponse(response, actionName) {
    var contentType = String(response.headers.get("content-type") || "").toLowerCase();
    var isJson = contentType.indexOf("application/json") >= 0;

    if (response.status === 401 || response.status === 403) {
      if (isJson) {
        return response.json().then(function (payload) {
          var authError = new Error(actionName + "_auth_required");
          authError.code = "auth_required";
          authError.status = response.status;
          authError.loginUrl = payload && payload.login_url ? payload.login_url : defaultLoginUrl();
          authError.payload = payload || {};
          throw authError;
        });
      }
      var unauthorizedError = new Error(actionName + "_auth_required");
      unauthorizedError.code = "auth_required";
      unauthorizedError.status = response.status;
      unauthorizedError.loginUrl = response.url || defaultLoginUrl();
      throw unauthorizedError;
    }

    if (!response.ok) {
      var httpError = new Error(actionName + "_http_" + response.status);
      httpError.status = response.status;
      httpError.contentType = contentType;
      httpError.redirected = !!response.redirected;
      httpError.responseUrl = response.url || "";
      throw httpError;
    }

    if (!isJson) {
      var contentTypeError = new Error(actionName + "_unexpected_content_type");
      contentTypeError.code = "unexpected_content_type";
      contentTypeError.contentType = contentType;
      contentTypeError.redirected = !!response.redirected;
      contentTypeError.responseUrl = response.url || "";
      if (response.redirected && response.url) {
        contentTypeError.loginUrl = response.url;
      }
      throw contentTypeError;
    }

    return response.json();
  }

  function handleToggleError(message, extra, error) {
    captureSocialError(message, extra, error);
    if (error && (error.code === "auth_required" || error.loginUrl)) {
      showToast("Нужно войти в аккаунт, чтобы продолжить", "warning");
      window.setTimeout(function () {
        window.location.href = error.loginUrl || defaultLoginUrl();
      }, 180);
      return;
    }
    showToast("Не удалось выполнить действие. Попробуйте еще раз.", "warning");
  }

  function initFavoriteToggles(root) {
    function syncFavoriteUi(productId, favorited) {
      document.querySelectorAll("[data-favorite-toggle][data-product-id='" + productId + "']").forEach(function (node) {
        node.classList.toggle("is-active", favorited);
        node.setAttribute("data-favorited", favorited ? "1" : "0");
        node.setAttribute("aria-pressed", favorited ? "true" : "false");
        node.setAttribute("title", favorited ? "Убрать из избранного" : "Избранное");
        node.setAttribute("aria-label", favorited ? "Убрать товар из избранного" : "Добавить в избранное");
      });
    }

    var scope = root || document;
    scope.querySelectorAll("[data-favorite-toggle]:not([data-fav-ready='1'])").forEach(function (btn) {
      btn.setAttribute("data-fav-ready", "1");
      btn.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        var pid = btn.getAttribute("data-product-id");
        if (!pid) return;
        fetch("/favorites/toggle/", {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": csrfToken()
          },
          body: "product_id=" + encodeURIComponent(pid)
        })
          .then(function (response) { return parseJsonResponse(response, "favorites_toggle"); })
          .then(function (data) {
            if (!data || !data.ok) {
              captureSocialError("favorites_toggle_rejected", { product_id: pid });
              showToast("Не удалось обновить избранное", "warning");
              return;
            }
            var on = !!data.favorited;
            syncFavoriteUi(pid, on);
            if (window.ServioAnalytics && data.tracking) {
              window.ServioAnalytics.push(data.tracking);
            }
          })
          .catch(function (error) {
            handleToggleError("favorites_toggle_failed", { product_id: pid }, error);
          });
      });
    });
  }

  function initSubscriptionToggles(root) {
    var scope = root || document;
    scope.querySelectorAll("[data-subscription-toggle]:not([data-subscription-ready='1'])").forEach(function (btn) {
      btn.setAttribute("data-subscription-ready", "1");
      btn.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        var entity = btn.getAttribute("data-entity");
        var entityId = btn.getAttribute("data-entity-id");
        if (!entity || !entityId) return;

        fetch("/subscriptions/toggle/", {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": csrfToken()
          },
          body: "entity=" + encodeURIComponent(entity) + "&entity_id=" + encodeURIComponent(entityId)
        })
          .then(function (response) { return parseJsonResponse(response, "subscriptions_toggle"); })
          .then(function (data) {
            if (!data || !data.ok) {
              captureSocialError("subscriptions_toggle_rejected", { entity: entity, entity_id: entityId });
              showToast("Не удалось обновить подписку", "warning");
              return;
            }
            var active = !!data.subscribed;
            btn.classList.toggle("is-active", active);
            btn.setAttribute("data-active", active ? "1" : "0");
            var textNode = btn.querySelector("[data-subscription-label]");
            if (textNode) {
              if (entity === "brand") {
                textNode.textContent = active ? "Подписка активна" : "Подписаться на бренд";
              } else if (entity === "category") {
                textNode.textContent = active ? "Подписка на категорию включена" : "Подписаться на категорию";
              }
            } else if (entity === "brand") {
              btn.textContent = active ? "Подписка активна" : "Подписаться на бренд";
            } else if (entity === "category") {
              btn.textContent = active ? "Подписка на категорию включена" : "Подписаться на категорию";
            }
          })
          .catch(function (error) {
            handleToggleError("subscriptions_toggle_failed", { entity: entity, entity_id: entityId }, error);
          });
      });
    });
  }

  function syncCompareUi(payload) {
    if (!payload) return;
    var compareCount = payload.compare_count || 0;
    document.querySelectorAll("[data-compare-count]").forEach(function (el) {
      el.textContent = String(compareCount);
    });
    document.querySelectorAll("[data-compare-badge]").forEach(function (el) {
      el.classList.toggle("is-hidden", compareCount < 1);
      if (compareCount < 1) {
        el.setAttribute("hidden", "hidden");
      } else {
        el.removeAttribute("hidden");
      }
    });
    document.querySelectorAll("[data-compare-launcher]").forEach(function (el) {
      el.classList.toggle("is-hidden", compareCount < 1);
      if (compareCount < 1) {
        el.setAttribute("hidden", "hidden");
        el.setAttribute("aria-hidden", "true");
      } else {
        el.removeAttribute("hidden");
        el.removeAttribute("aria-hidden");
      }
    });
    document.querySelectorAll("[data-compare-tray]").forEach(function (el) {
      el.classList.toggle("is-hidden", compareCount < 1);
      if (compareCount < 1) {
        el.setAttribute("hidden", "hidden");
        el.setAttribute("aria-hidden", "true");
      } else {
        el.removeAttribute("hidden");
        el.removeAttribute("aria-hidden");
      }
    });
    document.querySelectorAll("[data-compare-tray-hint]").forEach(function (el) {
      el.textContent = compareCount < 2
        ? "Добавьте ещё товары, чтобы увидеть отличия по ETA, MOQ и документам."
        : "Откройте tray или переходите в полный compare для decision check.";
    });
    if (Array.isArray(payload.compare_items)) {
      document.querySelectorAll("[data-compare-tray-items]").forEach(function (container) {
        container.innerHTML = payload.compare_items.map(function (item) {
          var brand = item.brand_name ? "<span>" + escapeHtml(item.brand_name) + "</span>" : "";
          return (
            "<a class=\"compare-tray-2026__item\" href=\"/products/" + encodeURIComponent(item.slug) + "/\">" +
            "<strong>" + escapeHtml(item.name) + "</strong>" +
            brand +
            "</a>"
          );
        }).join("");
      });
    }
    if (Array.isArray(payload.compare_ids)) {
      document.querySelectorAll("[data-compare-toggle]").forEach(function (btn) {
        var pid = parseInt(btn.getAttribute("data-product-id") || "0", 10);
        if (!pid) return;
        var inCompare = payload.compare_ids.indexOf(pid) >= 0;
        btn.classList.toggle("is-active", inCompare);
        btn.setAttribute("data-in-compare", inCompare ? "1" : "0");
        btn.setAttribute("aria-pressed", inCompare ? "true" : "false");
        btn.setAttribute("title", inCompare ? "Убрать из сравнения" : "Сравнить");
        btn.setAttribute("aria-label", inCompare ? "Убрать товар из сравнения" : "Сравнить товар");
        var label = btn.querySelector("[data-compare-label]");
        if (label) {
          label.textContent = inCompare
            ? (btn.getAttribute("data-compare-label-active") || "Убрать")
            : (btn.getAttribute("data-compare-label-inactive") || "Добавить");
        }
      });
    }
  }

  function initCompareToggles(root) {
    var scope = root || document;
    scope.querySelectorAll("[data-compare-toggle]:not([data-compare-ready='1'])").forEach(function (btn) {
      btn.setAttribute("data-compare-ready", "1");
      btn.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        var pid = btn.getAttribute("data-product-id");
        if (!pid) return;
        fetch("/compare/toggle/", {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": csrfToken()
          },
          body: "product_id=" + encodeURIComponent(pid)
        })
          .then(function (response) { return parseJsonResponse(response, "compare_toggle"); })
          .then(function (data) {
            if (!data || !data.ok) {
              captureSocialError("compare_toggle_rejected", { product_id: pid });
              showToast("Не удалось обновить сравнение", "warning");
              return;
            }
            syncCompareUi(data);
            if (window.ServioAnalytics && data.tracking) {
              window.ServioAnalytics.push(data.tracking);
            }
          })
          .catch(function (error) {
            handleToggleError("compare_toggle_failed", { product_id: pid }, error);
          });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initFavoriteToggles(document);
    initSubscriptionToggles(document);
    initCompareToggles(document);
  });
  document.body.addEventListener("htmx:load", function (event) {
    var root = event.detail && event.detail.elt ? event.detail.elt : document;
    initFavoriteToggles(root);
    initSubscriptionToggles(root);
    initCompareToggles(root);
  });
})();
