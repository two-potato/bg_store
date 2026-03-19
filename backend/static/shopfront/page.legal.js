(function(){
  function isActive(){
    return window.ServioRuntime && window.ServioRuntime.isPageType('account_legal');
  }

  function syncLegalConfirm(root){
    if (!isActive()) return;
    var scope = root || document;
    var chk = scope.querySelector('[data-legal-confirm]');
    var btn = scope.querySelector('[data-legal-submit]');
    if (!chk || !btn) return;
    btn.disabled = !chk.checked;
  }

  function handleInnPreviewSwap(e){
    if (!(e.target && e.target.id === 'inn-preview')) return;
    var box = document.getElementById('inn-preview');
    var named = box ? box.querySelector('[data-name]') : null;
    if (!named) return;
    var name = named.getAttribute('data-name') || '';
    if (!name) return;
    var nameInput = document.querySelector("input[name='name']");
    if (nameInput && !nameInput.value) nameInput.value = name;
  }

  var pollMs = 5000;
  var timer = null;

  function runPoll(){
    if (!isActive()) return;
    if (!document.getElementById('memberships') && !document.getElementById('legal-requests')) {
      pollMs = 5000;
      return scheduleNext();
    }
    if (document.hidden) {
      pollMs = Math.min(pollMs * 2, 30000);
      return scheduleNext();
    }
    document.body.dispatchEvent(new Event('legalPoll'));
    pollMs = 5000;
    scheduleNext();
  }

  function scheduleNext(){
    clearTimeout(timer);
    timer = setTimeout(runPoll, pollMs);
  }

  function ensurePolling(){
    pollMs = 5000;
    scheduleNext();
  }

  document.addEventListener('change', function(e){
    if (!isActive()) return;
    if (e.target && e.target.matches('[data-legal-confirm]')) {
      syncLegalConfirm(document);
    }
  });
  document.body.addEventListener('htmx:afterSwap', function(e){
    if (!isActive()) return;
    handleInnPreviewSwap(e);
  });
  document.addEventListener('visibilitychange', function(){
    if (!isActive()) return;
    if (!document.hidden) document.body.dispatchEvent(new Event('legalPoll'));
  });
  document.addEventListener('DOMContentLoaded', function(){
    syncLegalConfirm(document);
    ensurePolling();
  });
  document.body.addEventListener('servio:page-enter', function(e){
    var root = e.detail && e.detail.root ? e.detail.root : document;
    syncLegalConfirm(root);
    ensurePolling();
  });
})();
