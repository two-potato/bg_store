// Minimal helpers for Telegram WebApp (no heavy JS)
(function(){
  const tg = window.Telegram && window.Telegram.WebApp;
  if (!tg) return;

  try { tg.expand(); tg.ready(); } catch (e) {}

  function applyTheme(){
    try {
      const isDark = tg.colorScheme === "dark";
      const root = document.getElementById("twa-root") || document.body;
      root.classList.remove("dark","light");
      root.classList.add(isDark ? "dark" : "light");
    } catch(e) {}
  }
  applyTheme();
  try { tg.onEvent('themeChanged', applyTheme); } catch (e) {}

  // Very tiny API used from templates if needed
  window.TWA = {
    setMainButton(text, onClickHref){
      try {
        tg.MainButton.setText(text || 'Продолжить');
        tg.MainButton.show();
        tg.MainButton.onClick(() => {
          if (!onClickHref) return;
          // navigate via HTMX if available
          const a = document.createElement('a');
          a.setAttribute('href', onClickHref);
          a.setAttribute('hx-get', onClickHref);
          a.setAttribute('hx-target', '#page');
          a.setAttribute('hx-swap', 'innerHTML');
          document.body.appendChild(a);
          a.click();
          a.remove();
        });
      } catch(e) {}
    },
    hideMainButton(){ try { tg.MainButton.hide(); } catch(e){} },
    alert(msg){ try { tg.showAlert(msg); } catch(e){} },
    haptic(kind){ try { tg.HapticFeedback.impactOccurred(kind || 'light'); } catch(e){} },
    initData(){ try { return tg.initData || ''; } catch(e){ return ''; } },
    initDataUnsafe(){ try { return tg.initDataUnsafe || {}; } catch(e){ return {}; } }
  };

  // Auto-login to Django via WebApp initData once per session
  try {
    const flagKey = 'twaLogged';
    const hasInit = !!(tg && (tg.initData || tg.initDataUnsafe));
    if (hasInit && !sessionStorage.getItem(flagKey)) {
      const initData = (tg.initData || '').toString();
      if (initData) {
        const csrf = (document.querySelector('meta[name="csrf-token"]')||{}).content || '';
        fetch('/account/twa/login/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf },
          body: new URLSearchParams({ initData })
        }).finally(() => { sessionStorage.setItem(flagKey, '1'); });
      }
    }
  } catch (e) {}

  // Fill Telegram login hidden field when present
  try {
    const input = document.getElementById('twa-initData');
    if (input && tg.initData) input.value = tg.initData;
  } catch (e) {}

  // Declarative haptic feedback and main button setup
  document.body.addEventListener('click', function(e){
    const node = e.target.closest('[data-twa-haptic]');
    if (!node) return;
    const kind = node.getAttribute('data-twa-haptic') || 'light';
    try { tg.HapticFeedback.impactOccurred(kind); } catch (err) {}
  });

  try {
    const btnCfg = document.querySelector('[data-twa-main-button]');
    if (btnCfg) {
      const text = btnCfg.getAttribute('data-twa-main-text') || 'Продолжить';
      const href = btnCfg.getAttribute('data-twa-main-href') || '/';
      window.TWA.setMainButton(text, href);
    }
  } catch (e) {}
})();
