(function(){
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

    var node = document.createElement('div');
    node.className = cardClass(variant);
    node.setAttribute('role', variant === 'danger' ? 'alert' : 'status');
    node.style.setProperty('--toast-duration', duration + 'ms');

    var icon = document.createElement('div');
    icon.className = 'toast-card__icon';
    icon.innerHTML = iconSvg(variant);

    var body = document.createElement('div');
    body.className = 'toast-card__body';

    var message = document.createElement('div');
    message.className = 'toast-card__message';
    message.textContent = msg;

    var progress = document.createElement('div');
    progress.className = 'toast-card__progress';
    progress.setAttribute('aria-hidden', 'true');

    body.appendChild(message);
    body.appendChild(progress);

    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'toast-close';
    close.setAttribute('aria-label', 'Закрыть уведомление');
    close.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 6l12 12M18 6l-12 12"></path></svg>';

    node.appendChild(icon);
    node.appendChild(body);
    node.appendChild(close);
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

    close.addEventListener('click', hide, { once: true });
    node.addEventListener('mouseenter', pauseTimer);
    node.addEventListener('mouseleave', resumeTimer);
    node.addEventListener('focusin', pauseTimer);
    node.addEventListener('focusout', resumeTimer);
    startTimer(duration);
  }

  document.body.addEventListener('showToast', function(e){ showToast(e.detail || {}); });
  window.ShopToast = { show: showToast };
})();
