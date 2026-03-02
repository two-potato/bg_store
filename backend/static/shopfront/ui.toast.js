(function(){
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  var MAX_TOASTS = 4;
  var DURATION_MS = 3200;

  function cardClass(variant) {
    if (variant === 'danger') return 'toast-card is-danger';
    if (variant === 'success') return 'toast-card is-success';
    return 'toast-card is-info';
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

    var stack = document.getElementById('toast-stack');
    if (!stack) return;

    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<div class="' + cardClass(variant) + '" role="status">' +
        '<div class="toast-card__message">' + escapeHtml(msg) + '</div>' +
        '<button type="button" class="toast-close" aria-label="Закрыть">✕</button>' +
      '</div>';

    var node = wrap.firstElementChild;
    stack.appendChild(node);
    pruneOldToasts(stack);

    var hide = function(){
      if (!node || !node.parentNode) return;
      node.classList.add('is-hiding');
      setTimeout(function(){
        node.remove();
      }, 180);
    };

    node.querySelector('.toast-close')?.addEventListener('click', hide, { once: true });
    setTimeout(hide, DURATION_MS);
  }

  document.body.addEventListener('showToast', function(e){ showToast(e.detail || {}); });
  window.ShopToast = { show: showToast };
})();
