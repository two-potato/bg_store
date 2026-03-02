(function(){
  function revealIn(root){
    var scope = root || document;
    var els = scope.querySelectorAll('.reveal:not([data-revealed="1"])');
    if (!('IntersectionObserver' in window) || els.length === 0) return;
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(entry){
        if (!entry.isIntersecting) return;
        var target = entry.target;
        var anim = target.getAttribute('data-anim') || 'animate__fadeInUp';
        target.classList.add('animate__animated', anim);
        target.setAttribute('data-revealed', '1');
        io.unobserve(target);
      });
    }, { threshold: 0.12 });
    els.forEach(function(el){ io.observe(el); });
  }

  function applyBreakpoint(){
    var root = document.body;
    if (!root) return;
    if (window.matchMedia('(min-width: 1024px)').matches) {
      root.classList.add('is-desktop');
      root.classList.remove('is-mobile');
    } else {
      root.classList.add('is-mobile');
      root.classList.remove('is-desktop');
    }
  }

  function init(root){
    revealIn(root);
    applyBreakpoint();
    initProductCarousels(root);
  }

  function clearLiveSearch(){
    var panel = document.getElementById('live-search-results');
    if (panel) panel.innerHTML = '';
  }

  function initLiveSearchDismiss(){
    document.addEventListener('keydown', function(e){
      if (e.key === 'Escape') clearLiveSearch();
    });
    document.addEventListener('click', function(e){
      var searchWrap = e.target && e.target.closest ? e.target.closest('.site-header-v2__search-wrap') : null;
      if (!searchWrap) clearLiveSearch();
    });
  }

  function setCarouselIndex(carousel, nextIndex){
    var track = carousel.querySelector('.product-card-carousel__track');
    if (!track) return;
    var count = parseInt(track.getAttribute('data-count') || '1', 10);
    if (!count || count < 2) return;
    if (nextIndex < 0) nextIndex = count - 1;
    if (nextIndex >= count) nextIndex = 0;
    track.setAttribute('data-index', String(nextIndex));
    track.style.transform = 'translateX(-' + (nextIndex * 100) + '%)';
    var dots = carousel.querySelectorAll('.product-card-carousel__dot');
    dots.forEach(function(dot){
      dot.classList.toggle('is-active', String(nextIndex) === dot.getAttribute('data-index'));
    });
  }

  function initProductCarousels(root){
    var scope = root || document;
    var carousels = scope.querySelectorAll('.product-card-carousel:not([data-carousel-ready="1"])');
    carousels.forEach(function(carousel){
      carousel.setAttribute('data-carousel-ready', '1');
      var prev = carousel.querySelector('[data-carousel-prev]');
      var next = carousel.querySelector('[data-carousel-next]');
      var dots = carousel.querySelectorAll('.product-card-carousel__dot');
      var track = carousel.querySelector('.product-card-carousel__track');
      if (!track) return;
      setCarouselIndex(carousel, parseInt(track.getAttribute('data-index') || '0', 10));

      if (prev) {
        prev.addEventListener('click', function(e){
          e.preventDefault();
          e.stopPropagation();
          var idx = parseInt(track.getAttribute('data-index') || '0', 10);
          setCarouselIndex(carousel, idx - 1);
        });
      }
      if (next) {
        next.addEventListener('click', function(e){
          e.preventDefault();
          e.stopPropagation();
          var idx = parseInt(track.getAttribute('data-index') || '0', 10);
          setCarouselIndex(carousel, idx + 1);
        });
      }
      dots.forEach(function(dot){
        dot.addEventListener('click', function(e){
          e.preventDefault();
          e.stopPropagation();
          setCarouselIndex(carousel, parseInt(dot.getAttribute('data-index') || '0', 10));
        });
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function(){ init(document); });
  document.body.addEventListener('htmx:load', function(e){ init(e.detail && e.detail.elt ? e.detail.elt : document); });
  window.addEventListener('resize', applyBreakpoint);
  initLiveSearchDismiss();
})();
