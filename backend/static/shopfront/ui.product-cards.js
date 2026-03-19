(function () {
  function setCarouselIndex(carousel, nextIndex) {
    var track = carousel.querySelector(".product-card-carousel__track");
    if (!track) return;
    var count = parseInt(track.getAttribute("data-count") || "1", 10);
    if (!count || count < 2) return;
    if (nextIndex < 0) nextIndex = count - 1;
    if (nextIndex >= count) nextIndex = 0;
    track.setAttribute("data-index", String(nextIndex));
    track.style.transform = "translateX(-" + (nextIndex * 100) + "%)";
    var dots = carousel.querySelectorAll(".product-card-carousel__dot");
    dots.forEach(function (dot) {
      dot.classList.toggle("is-active", String(nextIndex) === dot.getAttribute("data-index"));
    });
  }

  function initProductCarousels(root) {
    var scope = root || document;
    var carousels = scope.querySelectorAll(".product-card-carousel:not([data-carousel-ready='1'])");
    carousels.forEach(function (carousel) {
      carousel.setAttribute("data-carousel-ready", "1");
      var prev = carousel.querySelector("[data-carousel-prev]");
      var next = carousel.querySelector("[data-carousel-next]");
      var dots = carousel.querySelectorAll(".product-card-carousel__dot");
      var track = carousel.querySelector(".product-card-carousel__track");
      if (!track) return;
      setCarouselIndex(carousel, parseInt(track.getAttribute("data-index") || "0", 10));

      if (prev) {
        prev.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          var idx = parseInt(track.getAttribute("data-index") || "0", 10);
          setCarouselIndex(carousel, idx - 1);
        });
      }
      if (next) {
        next.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          var idx = parseInt(track.getAttribute("data-index") || "0", 10);
          setCarouselIndex(carousel, idx + 1);
        });
      }
      dots.forEach(function (dot) {
        dot.addEventListener("click", function (event) {
          event.preventDefault();
          event.stopPropagation();
          setCarouselIndex(carousel, parseInt(dot.getAttribute("data-index") || "0", 10));
        });
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initProductCarousels(document);
  });
  document.body.addEventListener("htmx:load", function (event) {
    initProductCarousels(event.detail && event.detail.elt ? event.detail.elt : document);
  });
})();
