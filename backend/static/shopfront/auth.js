(function () {
  function isActive() {
    return window.ServioRuntime && (window.ServioRuntime.isPageType("login") || window.ServioRuntime.isPageType("register"));
  }

  function bindPasswordToggles(scope) {
    if (!isActive()) return;
    var root = scope || document;
    var buttons = root.querySelectorAll("[data-password-toggle]");
    buttons.forEach(function (btn) {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", function () {
        var wrap = btn.closest(".relative") || btn.parentElement;
        if (!wrap) return;
        var input = wrap.querySelector("[data-password-input]");
        if (!input) return;
        var show = input.type === "password";
        input.type = show ? "text" : "password";
        btn.textContent = show ? "Скрыть" : "Показать";
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      bindPasswordToggles(document);
    });
  } else {
    bindPasswordToggles(document);
  }

  document.body.addEventListener("servio:page-enter", function (evt) {
    var root = evt.detail && evt.detail.root ? evt.detail.root : document;
    bindPasswordToggles(root);
  });
})();
