(function () {
  function bindPasswordToggles(scope) {
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

  document.body.addEventListener("htmx:afterSwap", function (evt) {
    bindPasswordToggles(evt.target || document);
  });
})();
