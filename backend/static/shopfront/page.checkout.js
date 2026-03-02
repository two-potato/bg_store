(function(){
  function syncCheckout(root){
    var scope = root || document;
    var wrap = scope.querySelector('[data-checkout-form]');
    if (!wrap) return;

    var ind = wrap.querySelector('#individual-fields');
    var comp = wrap.querySelector('#company-fields');
    var checked = wrap.querySelector('input[name="customer_type"]:checked');
    if (!ind || !comp || !checked) return;

    if (checked.value === 'company') {
      comp.classList.remove('hidden');
      ind.classList.add('hidden');
    } else {
      ind.classList.remove('hidden');
      comp.classList.add('hidden');
    }
  }

  document.addEventListener('change', function(e){
    if (e.target && e.target.matches('input[name="customer_type"]')) {
      syncCheckout(document);
    }
  });

  document.addEventListener('DOMContentLoaded', function(){ syncCheckout(document); });
  document.body.addEventListener('htmx:load', function(e){ syncCheckout(e.detail && e.detail.elt ? e.detail.elt : document); });
})();
