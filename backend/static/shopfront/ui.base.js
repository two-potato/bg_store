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
    initFavoriteToggles(root);
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

  function initFilterDropdown(){
    document.addEventListener('click', function(e){
      var closeBtn = e.target && e.target.closest ? e.target.closest('[data-filter-close]') : null;
      if (!closeBtn) return;
      var details = closeBtn.closest ? closeBtn.closest('[data-filter-dropdown]') : null;
      if (!details) return;
      details.removeAttribute('open');
    });

    document.addEventListener('keydown', function(e){
      if (e.key !== 'Escape') return;
      document.querySelectorAll('[data-filter-dropdown][open]').forEach(function(node){
        node.removeAttribute('open');
      });
    });
  }

  function initMobileHeaderMenu(){
    document.addEventListener('click', function(e){
      var summary = e.target && e.target.closest ? e.target.closest('.site-mobile-user-menu > summary') : null;
      if (!summary) return;
      var details = summary.parentElement;
      if (!details) return;
      e.preventDefault();
      var isOpen = details.hasAttribute('open');
      document.querySelectorAll('.site-mobile-user-menu[open]').forEach(function(node){
        if (node !== details) node.removeAttribute('open');
      });
      if (isOpen) details.removeAttribute('open');
      else details.setAttribute('open', '');
    });

    document.addEventListener('click', function(e){
      var inside = e.target && e.target.closest ? e.target.closest('.site-mobile-user-menu') : null;
      if (inside) return;
      document.querySelectorAll('.site-mobile-user-menu[open]').forEach(function(node){
        node.removeAttribute('open');
      });
    });

    document.addEventListener('keydown', function(e){
      if (e.key !== 'Escape') return;
      document.querySelectorAll('.site-mobile-user-menu[open]').forEach(function(node){
        node.removeAttribute('open');
      });
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

  function getCookie(name){
    var value = '; ' + document.cookie;
    var parts = value.split('; ' + name + '=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }

  function initFavoriteToggles(root){
    var scope = root || document;
    scope.querySelectorAll('[data-favorite-toggle]:not([data-fav-ready="1"])').forEach(function(btn){
      btn.setAttribute('data-fav-ready', '1');
      btn.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        var pid = btn.getAttribute('data-product-id');
        if (!pid) return;
        fetch('/favorites/toggle/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'X-CSRFToken': getCookie('csrftoken')
          },
          body: 'product_id=' + encodeURIComponent(pid)
        })
          .then(function(r){ return r.json(); })
          .then(function(data){
            if (!data || !data.ok) return;
            var on = !!data.favorited;
            btn.classList.toggle('is-active', on);
            btn.setAttribute('data-favorited', on ? '1' : '0');
          })
          .catch(function(){});
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function(){ init(document); });
  document.body.addEventListener('htmx:load', function(e){ init(e.detail && e.detail.elt ? e.detail.elt : document); });
  window.addEventListener('resize', applyBreakpoint);
  initLiveSearchDismiss();
  initFilterDropdown();
  initMobileHeaderMenu();
})();
