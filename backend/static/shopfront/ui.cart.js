(function(){
  var STORAGE_KEY = 'bg_cart_qty_map_v1';

  function readQtyMap(){
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') || {};
    } catch (_) {
      return {};
    }
  }

  function writeQtyMap(map){
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(map || {})); } catch (_) {}
  }

  function resetAllCartControls(){
    document.querySelectorAll('.cart-control[data-pid]').forEach(function(node){
      applyQtyState(node, 0);
    });
    writeQtyMap({});
  }

  function applyQtyState(node, qty){
    if (!node) return;
    var addBtn = node.querySelector('.add');
    var step = node.querySelector('.stepper');
    var label = node.querySelector('.qty');
    if (qty > 0) {
      node.classList.add('is-in-cart');
      addBtn?.classList.add('hidden');
      if (addBtn?.style) addBtn.style.setProperty('display', 'none', 'important');
      if (step) {
        step.classList.remove('hidden');
        if (step.style) step.style.setProperty('display', 'inline-flex', 'important');
      }
      if (label) label.textContent = String(qty);
    } else {
      node.classList.remove('is-in-cart');
      if (step) {
        step.classList.add('hidden');
        if (step.style) step.style.setProperty('display', 'none', 'important');
      }
      if (label) label.textContent = '0';
      addBtn?.classList.remove('hidden');
      if (addBtn?.style) addBtn.style.removeProperty('display');
    }
  }

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
    var badge = document.getElementById('cart-badge-inline') || document.getElementById('cart-badge');
    if (!badge || !iconO || !iconF) return;
    var cnt = getBadgeCount(badge);
    if (cnt > 0) {
      iconO.classList.add('hidden');
      iconF.classList.remove('hidden');
    } else {
      iconF.classList.add('hidden');
      iconO.classList.remove('hidden');
    }
  }

  function reconcileByBadge(){
    var badge = document.getElementById('cart-badge-inline') || document.getElementById('cart-badge');
    if (!badge) return;
    var cnt = getBadgeCount(badge);
    if (cnt <= 0) {
      resetAllCartControls();
    }
  }

  function bumpBadge() {
    var b = document.getElementById('cart-badge-inline') || document.getElementById('cart-badge');
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

    var map = readQtyMap();
    if (qty > 0) map[pid] = qty;
    else delete map[pid];
    writeQtyMap(map);

    document.querySelectorAll('.cart-control[data-pid="' + pid + '"]').forEach(function(node){
      applyQtyState(node, qty);
    });
  }

  function parseQty(node){
    if (!node) return 0;
    var raw = node.querySelector('.qty')?.textContent || '0';
    var qty = parseInt(String(raw).trim(), 10);
    return Number.isFinite(qty) ? qty : 0;
  }

  function hydrateCartControls(){
    var map = readQtyMap();
    document.querySelectorAll('.cart-control[data-pid]').forEach(function(node){
      var pid = String(node.getAttribute('data-pid') || '');
      if (!pid) return;
      var qty = parseInt(map[pid] || 0, 10) || 0;
      if (qty > 0) applyQtyState(node, qty);
    });
  }

  document.body.addEventListener('cartChanged', function(){
    bumpBadge();
    // Wait for OOB badge update and reconcile UI with real cart total.
    setTimeout(reconcileByBadge, 60);
  });
  document.body.addEventListener('click', function(e){
    var addBtn = e.target && e.target.closest ? e.target.closest('.cart-control .add') : null;
    if (addBtn) {
      var wrap = addBtn.closest('.cart-control[data-pid]');
      if (wrap) applyQtyState(wrap, Math.max(1, parseQty(wrap) || 1));
      return;
    }
    var stepBtn = e.target && e.target.closest ? e.target.closest('.cart-control .cart-step-btn') : null;
    if (!stepBtn) return;
    var form = stepBtn.closest('form');
    var wrap2 = stepBtn.closest('.cart-control[data-pid]');
    if (!form || !wrap2) return;
    var vals = form.getAttribute('hx-vals') || '';
    var isDec = vals.indexOf('\"op\":\"dec\"') !== -1;
    var isInc = vals.indexOf('\"op\":\"inc\"') !== -1;
    var cur = parseQty(wrap2);
    var next = cur;
    if (isDec) next = Math.max(0, cur - 1);
    if (isInc) next = cur + 1;
    applyQtyState(wrap2, next);
  });
  document.body.addEventListener('cartQtyUpdated', onCartQtyUpdated);
  document.body.addEventListener('htmx:afterSwap', function(e){
    var det = e.detail || {};
    var swapped =
      (e.target && (e.target.id === 'cart-badge' || e.target.id === 'cart-badge-inline')) ||
      (det.elt && (det.elt.id === 'cart-badge' || det.elt.id === 'cart-badge-inline')) ||
      (det.target && (det.target.id === 'cart-badge' || det.target.id === 'cart-badge-inline'));
    if (swapped) syncCartIcon();
    if (swapped) reconcileByBadge();
  });
  document.body.addEventListener('htmx:afterOnLoad', function(e){
    var det = e.detail || {};
    if (det.elt && (det.elt.id === 'cart-badge' || det.elt.id === 'cart-badge-inline')) {
      syncCartIcon();
      reconcileByBadge();
    }
  });
  document.body.addEventListener('htmx:afterRequest', syncCartIcon);
  document.addEventListener('DOMContentLoaded', function(){
    syncCartIcon();
    hydrateCartControls();
    reconcileByBadge();
  });
  document.body.addEventListener('htmx:load', function(){
    hydrateCartControls();
    reconcileByBadge();
  });
})();
