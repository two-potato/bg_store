(function () {
  function runtime() {
    return window.ServioRuntime || null;
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
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": runtime().getCookie("csrftoken")
          },
          body: "product_id=" + encodeURIComponent(pid)
        })
          .then(function (response) { return response.json(); })
          .then(function (data) {
            if (!data || !data.ok) return;
            var on = !!data.favorited;
            syncFavoriteUi(pid, on);
            if (window.ServioAnalytics && data.tracking) {
              window.ServioAnalytics.push(data.tracking);
            }
          })
          .catch(function () {});
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
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": runtime().getCookie("csrftoken")
          },
          body: "entity=" + encodeURIComponent(entity) + "&entity_id=" + encodeURIComponent(entityId)
        })
          .then(function (response) { return response.json(); })
          .then(function (data) {
            if (!data || !data.ok) return;
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
          .catch(function () {});
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
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "X-CSRFToken": runtime().getCookie("csrftoken")
          },
          body: "product_id=" + encodeURIComponent(pid)
        })
          .then(function (response) { return response.json(); })
          .then(function (data) {
            if (!data || !data.ok) return;
            syncCompareUi(data);
          })
          .catch(function () {});
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
