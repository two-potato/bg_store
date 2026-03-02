(function(){
  document.body.addEventListener('click', function(e){
    var btn = e.target.closest('[data-qty-action]');
    if (!btn) return;
    var inputId = btn.getAttribute('data-qty-target');
    if (!inputId) return;
    var input = document.getElementById(inputId);
    if (!input || input.disabled) return;

    var cur = parseInt(input.value || '1', 10) || 1;
    var min = parseInt(input.min || '1', 10) || 1;
    var max = parseInt(input.max || '999999', 10) || 999999;
    if (btn.getAttribute('data-qty-action') === 'dec') input.value = String(Math.max(min, cur - 1));
    if (btn.getAttribute('data-qty-action') === 'inc') input.value = String(Math.min(max, cur + 1));
  });
})();
