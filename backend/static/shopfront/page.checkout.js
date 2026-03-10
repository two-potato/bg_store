(function(){
  function isActive(){
    return window.ServioRuntime && window.ServioRuntime.isPageType('checkout');
  }

  function pushAnalytics(payload){
    if (!payload || !payload.event) return;
    try {
      document.body.dispatchEvent(new CustomEvent('analyticsEvent', { detail: payload }));
    } catch (_) {}
  }

  function cartSummary(form){
    var raw = form.getAttribute('data-checkout-cart') || '{}';
    try {
      return JSON.parse(raw);
    } catch (_) {
      return {};
    }
  }

  function selectedRadioValue(form, name){
    var checked = form.querySelector('input[name="' + name + '"]:checked');
    return checked ? checked.value : '';
  }

  function buildBasePayload(form){
    var summary = cartSummary(form);
    return {
      checkout_step: 'details',
      customer_type: selectedRadioValue(form, 'customer_type'),
      payment_method: selectedRadioValue(form, 'payment_method'),
      seller_count: summary.seller_count || 0,
      ecommerce: {
        currency: summary.currency || 'RUB',
        value: summary.value || 0,
        items: Array.isArray(summary.items) ? summary.items : [],
      },
    };
  }

  function syncCheckout(root){
    if (!isActive()) return;
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

  function bindCheckoutSubmit(root){
    if (!isActive()) return;
    var scope = root || document;
    var form = scope.querySelector('[data-checkout-form]');
    if (!form || form.getAttribute('data-submit-bound') === '1') return;
    form.setAttribute('data-submit-bound', '1');

    function setSubmitState(isBusy){
      var submit = form.querySelector('[data-checkout-submit]');
      if (!submit) return;
      if (isBusy) {
        submit.disabled = true;
        submit.setAttribute('aria-busy', 'true');
        submit.textContent = 'Отправляем...';
        return;
      }
      var cart = cartSummary(form);
      submit.disabled = !(((cart.items || []).length) > 0);
      submit.removeAttribute('aria-busy');
      submit.textContent = 'Оформить';
    }

    form.addEventListener('submit', function(e){
      if (!form.checkValidity()) {
        e.preventDefault();
        form.reportValidity();
        pushAnalytics(Object.assign({ event: 'checkout_error' }, buildBasePayload(form), {
          checkout_step: 'details',
          error_message: 'validation_failed',
        }));
        return;
      }
      pushAnalytics(Object.assign({ event: 'checkout_step_view' }, buildBasePayload(form), { checkout_step: 'submit_attempt' }));
      setSubmitState(true);
    });

    document.body.addEventListener('htmx:responseError', function(evt){
      if (!isActive()) return;
      if (evt.detail && evt.detail.requestConfig && evt.detail.requestConfig.elt === form) {
        setSubmitState(false);
      }
    });

    document.body.addEventListener('htmx:sendError', function(evt){
      if (!isActive()) return;
      if (evt.detail && evt.detail.requestConfig && evt.detail.requestConfig.elt === form) {
        setSubmitState(false);
      }
    });

    document.body.addEventListener('htmx:afterRequest', function(evt){
      if (!isActive()) return;
      if (evt.detail && evt.detail.requestConfig && evt.detail.requestConfig.elt === form && !evt.detail.successful) {
        setSubmitState(false);
      }
    });

    document.body.addEventListener('htmx:beforeSwap', function(evt){
      if (!isActive()) return;
      if (!evt.detail || !evt.detail.requestConfig || evt.detail.requestConfig.elt !== form) return;
      if (evt.detail.xhr && evt.detail.xhr.status === 422) {
        evt.detail.shouldSwap = true;
        evt.detail.isError = false;
      }
    });
  }

  document.addEventListener('change', function(e){
    if (!isActive()) return;
    if (e.target && e.target.matches('input[name="customer_type"]')) {
      syncCheckout(document);
      var form = e.target.closest('[data-checkout-form]');
      if (form) {
        pushAnalytics(Object.assign({ event: 'checkout_step_view' }, buildBasePayload(form), {
          checkout_step: 'customer_type_selected',
          selected_value: e.target.value,
        }));
      }
    }
    if (e.target && e.target.matches('input[name="payment_method"]')) {
      var paymentForm = e.target.closest('[data-checkout-form]');
      if (paymentForm) {
        pushAnalytics(Object.assign({ event: 'checkout_step_view' }, buildBasePayload(paymentForm), {
          checkout_step: 'payment_method_selected',
          selected_value: e.target.value,
        }));
      }
    }
    if (e.target && e.target.matches('[name="delivery_option"]')) {
      var deliveryForm = e.target.closest('[data-checkout-form]');
      if (deliveryForm) {
        pushAnalytics(Object.assign({ event: 'delivery_option_selected' }, buildBasePayload(deliveryForm), {
          delivery_option: e.target.value,
        }));
      }
    }
  });

  function initForRoot(root){
    syncCheckout(root || document);
    bindCheckoutSubmit(root || document);
  }

  document.addEventListener('DOMContentLoaded', function(){
    initForRoot(document);
  });
  document.body.addEventListener('servio:page-enter', function(e){
    var root = e.detail && e.detail.root ? e.detail.root : document;
    initForRoot(root);
  });
})();
