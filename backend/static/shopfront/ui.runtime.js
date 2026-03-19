(function () {
  function normalizePath(path) {
    if (!path) return "/";
    return path.length > 1 ? path.replace(/\/+$/, "") + "/" : path;
  }

  function resolvePageTypes(pathname) {
    var path = normalizePath(pathname || window.location.pathname || "/");
    var types = [];

    if (path === "/checkout/" || path.indexOf("/checkout/") === 0 || path.indexOf("/payments/fake/") === 0) {
      types.push("checkout");
    }
    if (path.indexOf("/product/") === 0) {
      types.push("product");
    }
    if (path === "/account/addresses/") {
      types.push("account_addresses");
    }
    if (path === "/account/legal/" || path.indexOf("/account/legal/") === 0) {
      types.push("account_legal");
    }
    if (path === "/account/login/" || path === "/account/register/") {
      types.push("auth");
    }
    if (path === "/account/login/") {
      types.push("login");
    }
    if (path === "/account/register/") {
      types.push("register");
    }
    if (!types.length) {
      types.push("page");
    }
    return types;
  }

  function getCurrentState() {
    return {
      path: normalizePath(window.location.pathname || "/"),
      pageTypes: resolvePageTypes(window.location.pathname || "/"),
    };
  }

  function getCookie(name) {
    var value = "; " + document.cookie;
    var parts = value.split("; " + name + "=");
    if (parts.length === 2) return parts.pop().split(";").shift();
    return "";
  }

  function showToast(message, variant) {
    try {
      document.body.dispatchEvent(new CustomEvent("showToast", {
        detail: { message: message, variant: variant || "success" }
      }));
    } catch (_) {}
  }

  function copyText(value) {
    if (!value) return Promise.reject(new Error("empty"));
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      return navigator.clipboard.writeText(value);
    }
    var field = document.createElement("textarea");
    field.value = value;
    field.setAttribute("readonly", "readonly");
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.appendChild(field);
    field.select();
    try {
      var ok = document.execCommand("copy");
      document.body.removeChild(field);
      return ok ? Promise.resolve() : Promise.reject(new Error("copy_failed"));
    } catch (err) {
      document.body.removeChild(field);
      return Promise.reject(err);
    }
  }

  function dispatchPageEnter(root) {
    var state = getCurrentState();
    if (document.body) {
      document.body.setAttribute("data-page-type", state.pageTypes[0] || "page");
      document.body.setAttribute("data-page-types", state.pageTypes.join(" "));
    }
    try {
      document.body.dispatchEvent(new CustomEvent("servio:page-enter", {
        detail: {
          path: state.path,
          pageTypes: state.pageTypes,
          root: root || document
        }
      }));
    } catch (_) {}
  }

  function isPageType(type) {
    return getCurrentState().pageTypes.indexOf(type) >= 0;
  }

  function onPageEnter(handler) {
    if (!document.body) return;
    document.body.addEventListener("servio:page-enter", function (event) {
      handler(event.detail || {});
    });
  }

  window.ServioRuntime = {
    current: getCurrentState,
    isPageType: isPageType,
    onPageEnter: onPageEnter,
    getCookie: getCookie,
    showToast: showToast,
    copyText: copyText,
    dispatchPageEnter: dispatchPageEnter,
  };

  document.addEventListener("DOMContentLoaded", function () {
    dispatchPageEnter(document);
  });
  document.body.addEventListener("htmx:load", function (event) {
    var root = event.detail && event.detail.elt ? event.detail.elt : document;
    dispatchPageEnter(root);
  });
  document.body.addEventListener("htmx:afterSettle", function (event) {
    var root = event.detail && event.detail.elt ? event.detail.elt : document;
    dispatchPageEnter(root);
  });
  window.addEventListener("popstate", function () {
    dispatchPageEnter(document);
  });
})();
