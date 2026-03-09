(function () {
  const KEY = "cookie_consent";
  const MAX_AGE = 60 * 60 * 24 * 365;
  const listeners = [];

  function setCookie(name, value) {
    document.cookie = name + "=" + encodeURIComponent(value) + "; Path=/; Max-Age=" + MAX_AGE + "; SameSite=Lax";
  }

  function getCookie(name) {
    const chunk = document.cookie.split("; ").find((row) => row.startsWith(name + "="));
    return chunk ? decodeURIComponent(chunk.split("=").slice(1).join("=")) : "";
  }

  function hideBanner(el) {
    el.classList.remove("is-visible");
    setTimeout(() => el.classList.add("hidden"), 180);
  }

  function emitChange(value) {
    listeners.forEach(function (listener) {
      try {
        listener(value);
      } catch (_) {}
    });
    try {
      document.dispatchEvent(new CustomEvent("servio:cookie-consent-changed", { detail: { value: value } }));
    } catch (_) {}
  }

  function persist(value) {
    localStorage.setItem(KEY, value);
    setCookie(KEY, value);
    emitChange(value);
  }

  function getState() {
    return localStorage.getItem(KEY) || getCookie(KEY) || "";
  }

  function init() {
    const banner = document.getElementById("cookie-consent");
    if (!banner) return;

    const saved = getState();
    if (saved === "accepted" || saved === "declined") {
      banner.classList.add("hidden");
      return;
    }

    banner.classList.remove("hidden");
    requestAnimationFrame(() => banner.classList.add("is-visible"));

    const accept = document.getElementById("cookie-consent-accept");
    const decline = document.getElementById("cookie-consent-decline");

    if (accept) {
      accept.addEventListener("click", function () {
        persist("accepted");
        hideBanner(banner);
      });
    }

    if (decline) {
      decline.addEventListener("click", function () {
        persist("declined");
        hideBanner(banner);
      });
    }
  }

  window.ServioConsent = {
    get: getState,
    set: persist,
    onChange: function (listener) {
      if (typeof listener === "function") listeners.push(listener);
    },
  };

  document.addEventListener("DOMContentLoaded", init);
})();
