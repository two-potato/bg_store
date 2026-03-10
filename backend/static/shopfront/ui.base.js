(function () {
  function revealIn(root) {
    var scope = root || document;
    var els = scope.querySelectorAll(".reveal:not([data-revealed='1'])");
    if (!("IntersectionObserver" in window) || els.length === 0) return;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var target = entry.target;
        var anim = target.getAttribute("data-anim") || "animate__fadeInUp";
        target.classList.add("animate__animated", anim);
        target.setAttribute("data-revealed", "1");
        io.unobserve(target);
      });
    }, { threshold: 0.12 });
    els.forEach(function (el) { io.observe(el); });
  }

  function applyBreakpoint() {
    var root = document.body;
    if (!root) return;
    if (window.matchMedia("(min-width: 1024px)").matches) {
      root.classList.add("is-desktop");
      root.classList.remove("is-mobile");
    } else {
      root.classList.add("is-mobile");
      root.classList.remove("is-desktop");
    }
  }

  function init(root) {
    revealIn(root);
    applyBreakpoint();
  }

  document.addEventListener("DOMContentLoaded", function () {
    init(document);
  });
  document.body.addEventListener("htmx:load", function (event) {
    init(event.detail && event.detail.elt ? event.detail.elt : document);
  });
  window.addEventListener("resize", applyBreakpoint);
})();
