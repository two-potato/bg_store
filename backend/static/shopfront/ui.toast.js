(function(){
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  var MAX_TOASTS = 5;
  var DURATION_MS = 4200;

  function cardClass(variant) {
    if (variant === 'danger') return 'toast-card toast-card--danger';
    if (variant === 'success') return 'toast-card toast-card--success';
    return 'toast-card toast-card--info';
  }

  function iconSvg(variant) {
    if (variant === 'danger') {
      return '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 9v4"></path><path d="M12 17h.01"></path><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.72 3h16.92a2 2 0 0 0 1.72-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path></svg>';
    }
    if (variant === 'success') {
      return '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20 6L9 17l-5-5"></path></svg>';
    }
    return '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 8h.01"></path><path d="M11 12h1v4h1"></path><circle cx="12" cy="12" r="9"></circle></svg>';
  }

  function pruneOldToasts(stack) {
    var cards = stack.querySelectorAll('.toast-card');
    while (cards.length > MAX_TOASTS) {
      cards[0].remove();
      cards = stack.querySelectorAll('.toast-card');
    }
  }

  function showToast(data) {
    var msg = (data && data.message) ? data.message : 'Готово';
    var variant = (data && data.variant) || 'neutral';
    var duration = Math.max(2200, Number(data && data.duration) || DURATION_MS);

    var stack = document.getElementById('toast-stack');
    if (!stack) return;

    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<div class="' + cardClass(variant) + '" role="' + (variant === 'danger' ? 'alert' : 'status') + '" style="--toast-duration:' + duration + 'ms">' +
        '<div class="toast-card__icon">' + iconSvg(variant) + '</div>' +
        '<div class="toast-card__body">' +
          '<div class="toast-card__message">' + escapeHtml(msg) + '</div>' +
          '<div class="toast-card__progress" aria-hidden="true"></div>' +
        '</div>' +
        '<button type="button" class="toast-close" aria-label="Закрыть уведомление">' +
          '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 6l12 12M18 6l-12 12"></path></svg>' +
        '</button>' +
      '</div>';

    var node = wrap.firstElementChild;
    stack.appendChild(node);
    pruneOldToasts(stack);

    var remaining = duration;
    var hideTimer = null;
    var startAt = Date.now();

    var hide = function(){
      if (!node || !node.parentNode) return;
      node.classList.add('is-hiding');
      setTimeout(function(){
        node.remove();
      }, 220);
    };

    var startTimer = function(ms){
      startAt = Date.now();
      hideTimer = setTimeout(hide, ms);
    };

    var pauseTimer = function(){
      if (!hideTimer) return;
      clearTimeout(hideTimer);
      hideTimer = null;
      remaining = Math.max(0, remaining - (Date.now() - startAt));
      node.classList.add('is-paused');
    };

    var resumeTimer = function(){
      if (hideTimer || remaining <= 0) return;
      node.classList.remove('is-paused');
      startTimer(remaining);
    };

    node.querySelector('.toast-close')?.addEventListener('click', hide, { once: true });
    node.addEventListener('mouseenter', pauseTimer);
    node.addEventListener('mouseleave', resumeTimer);
    node.addEventListener('focusin', pauseTimer);
    node.addEventListener('focusout', resumeTimer);
    startTimer(duration);
  }

  document.body.addEventListener('showToast', function(e){ showToast(e.detail || {}); });
  window.ShopToast = { show: showToast };
})();
