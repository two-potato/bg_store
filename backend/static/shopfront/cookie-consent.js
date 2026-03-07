(function () {
  const KEY = "cookie_consent";
  const MAX_AGE = 60 * 60 * 24 * 365;

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

  function init() {
    const banner = document.getElementById("cookie-consent");
    if (!banner) return;

    const saved = localStorage.getItem(KEY) || getCookie(KEY);
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
        localStorage.setItem(KEY, "accepted");
        setCookie(KEY, "accepted");
        hideBanner(banner);
      });
    }

    if (decline) {
      decline.addEventListener("click", function () {
        localStorage.setItem(KEY, "declined");
        setCookie(KEY, "declined");
        hideBanner(banner);
      });
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
