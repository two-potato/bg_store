(function(){
  function getBadgeCount(badge) {
    if (!badge) return 0;
    var countNode = badge.querySelector('.cart-badge-count');
    if (countNode) {
      var d = parseInt((countNode.dataset.count || countNode.textContent || '0').trim(), 10);
      return Number.isFinite(d) ? d : 0;
    }
    var txt = (badge.textContent || '').trim();
    var m = txt.match(/\d+/);
    return m ? (parseInt(m[0], 10) || 0) : 0;
  }

  function syncCartIcon() {
    var iconO = document.getElementById('cart-icon-outline');
    var iconF = document.getElementById('cart-icon-filled');
    var badge = document.getElementById('cart-badge');
    if (!badge || !iconO || !iconF) return;
    var cnt = getBadgeCount(badge);
    if (cnt > 0) {
      iconO.classList.add('hidden');
      iconF.classList.remove('hidden');
      badge.classList.remove('hidden');
    } else {
      iconF.classList.add('hidden');
      iconO.classList.remove('hidden');
      badge.classList.add('hidden');
    }
  }

  function bumpBadge() {
    var b = document.getElementById('cart-badge');
    if (!b) return;
    b.classList.remove('animate__animated', 'animate__rubberBand');
    void b.offsetWidth;
    b.classList.add('animate__animated', 'animate__rubberBand');
  }

  function onCartQtyUpdated(e){
    var d = e.detail || {};
    var pid = String(d.product_id || '');
    var qty = parseInt(d.qty || 0, 10) || 0;
    if (!pid) return;

    document.querySelectorAll('.cart-control[data-pid="' + pid + '"]').forEach(function(node){
      var addBtn = node.querySelector('.add');
      var step = node.querySelector('.stepper');
      var label = node.querySelector('.qty');
      if (qty > 0) {
        addBtn?.classList.add('hidden');
        if (step) {
          step.classList.remove('hidden');
          step.classList.add('animate__animated', 'animate__fadeIn');
          setTimeout(function(){ step.classList.remove('animate__animated', 'animate__fadeIn'); }, 350);
        }
        if (label) label.textContent = String(qty);
      } else {
        step?.classList.add('hidden');
        if (addBtn) {
          addBtn.classList.remove('hidden');
          addBtn.classList.add('animate__animated', 'animate__fadeIn');
          setTimeout(function(){ addBtn.classList.remove('animate__animated', 'animate__fadeIn'); }, 350);
        }
      }
    });
  }

  document.body.addEventListener('cartChanged', function(){
    bumpBadge();
  });
  document.body.addEventListener('cartQtyUpdated', onCartQtyUpdated);
  document.body.addEventListener('htmx:afterSwap', function(e){
    var det = e.detail || {};
    var swapped = (e.target && e.target.id === 'cart-badge') || (det.elt && det.elt.id === 'cart-badge') || (det.target && det.target.id === 'cart-badge');
    if (swapped) syncCartIcon();
  });
  document.body.addEventListener('htmx:afterOnLoad', function(e){
    var det = e.detail || {};
    if (det.elt && det.elt.id === 'cart-badge') syncCartIcon();
  });
  document.body.addEventListener('htmx:afterRequest', syncCartIcon);
  document.addEventListener('DOMContentLoaded', function(){
    syncCartIcon();
  });
})();
