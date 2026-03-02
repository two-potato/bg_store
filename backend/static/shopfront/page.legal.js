(function(){
  function syncLegalConfirm(root){
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
    if (e.target && e.target.matches('[data-legal-confirm]')) {
      syncLegalConfirm(document);
    }
  });
  document.body.addEventListener('htmx:afterSwap', handleInnPreviewSwap);
  document.addEventListener('visibilitychange', function(){
    if (!document.hidden) document.body.dispatchEvent(new Event('legalPoll'));
  });
  document.addEventListener('DOMContentLoaded', function(){
    syncLegalConfirm(document);
    ensurePolling();
  });
  document.body.addEventListener('htmx:load', function(e){
    syncLegalConfirm(e.detail && e.detail.elt ? e.detail.elt : document);
    ensurePolling();
  });
})();
