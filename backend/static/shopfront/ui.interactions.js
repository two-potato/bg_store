(function () {
  function runtime() {
    return window.ServioRuntime || null;
  }

  function initFallbackImages() {
    if (document.body.getAttribute("data-image-fallback-bound") === "1") return;
    document.body.setAttribute("data-image-fallback-bound", "1");
    document.addEventListener("error", function (event) {
      var img = event.target;
      if (!img || img.tagName !== "IMG") return;
      var fallbackSrc = img.getAttribute("data-fallback-src");
      if (!fallbackSrc || img.getAttribute("data-fallback-applied") === "1") return;
      img.setAttribute("data-fallback-applied", "1");
      img.src = fallbackSrc;
    }, true);
  }

  function clearLiveSearch() {
    var desktopPanel = document.getElementById("live-search-results");
    var mobilePanel = document.getElementById("live-search-results-mobile");
    if (desktopPanel) desktopPanel.innerHTML = "";
    if (mobilePanel) mobilePanel.innerHTML = "";
  }

  function initLiveSearchDismiss() {
    if (document.body.getAttribute("data-live-search-dismiss-bound") === "1") return;
    document.body.setAttribute("data-live-search-dismiss-bound", "1");
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") clearLiveSearch();
    });
    document.addEventListener("click", function (event) {
      var searchWrap = event.target && event.target.closest ? event.target.closest(".site-header-v2__search-wrap") : null;
      if (!searchWrap) clearLiveSearch();
    });
  }

  function initFilterDropdown() {
    if (document.body.getAttribute("data-filter-dropdown-bound") === "1") return;
    document.body.setAttribute("data-filter-dropdown-bound", "1");
    document.addEventListener("click", function (event) {
      var closeBtn = event.target && event.target.closest ? event.target.closest("[data-filter-close]") : null;
      if (!closeBtn) return;
      var details = closeBtn.closest ? closeBtn.closest("[data-filter-dropdown]") : null;
      if (details) details.removeAttribute("open");
    });
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      document.querySelectorAll("[data-filter-dropdown][open]").forEach(function (node) {
        node.removeAttribute("open");
      });
    });
  }

  function initDesktopHeaderMenus() {
    if (document.body.getAttribute("data-desktop-header-menus-bound") === "1") return;
    document.body.setAttribute("data-desktop-header-menus-bound", "1");

    var selectors = [
      ".site-catalog-menu",
      ".site-header-v3__more-menu",
      ".site-header-v3__account-menu"
    ];

    function allMenus() {
      return document.querySelectorAll(selectors.join(","));
    }

    function closeAllMenus(exceptNode) {
      allMenus().forEach(function (node) {
        if (exceptNode && node === exceptNode) return;
        node.removeAttribute("open");
      });
    }

    document.addEventListener("click", function (event) {
      var summary = event.target && event.target.closest
        ? event.target.closest(".site-catalog-menu > summary, .site-header-v3__more-menu > summary, .site-header-v3__account-menu > summary")
        : null;

      if (summary) {
        var details = summary.parentElement;
        if (!details) return;
        event.preventDefault();
        var isOpen = details.hasAttribute("open");
        closeAllMenus(details);
        if (isOpen) details.removeAttribute("open");
        else details.setAttribute("open", "");
        return;
      }

      var insideMenu = event.target && event.target.closest ? event.target.closest(selectors.join(",")) : null;
      if (!insideMenu) closeAllMenus();
    });

    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      closeAllMenus();
    });
  }

  function initMobileHeaderMenu() {
    if (document.body.getAttribute("data-mobile-header-menu-bound") === "1") return;
    document.body.setAttribute("data-mobile-header-menu-bound", "1");
    document.addEventListener("click", function (event) {
      var summary = event.target && event.target.closest ? event.target.closest(".site-mobile-user-menu > summary") : null;
      if (!summary) return;
      var details = summary.parentElement;
      if (!details) return;
      event.preventDefault();
      var isOpen = details.hasAttribute("open");
      document.querySelectorAll(".site-mobile-user-menu[open]").forEach(function (node) {
        if (node !== details) node.removeAttribute("open");
      });
      if (isOpen) details.removeAttribute("open");
      else details.setAttribute("open", "");
    });
    document.addEventListener("click", function (event) {
      var inside = event.target && event.target.closest ? event.target.closest(".site-mobile-user-menu") : null;
      if (inside) return;
      document.querySelectorAll(".site-mobile-user-menu[open]").forEach(function (node) {
        node.removeAttribute("open");
      });
    });
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      document.querySelectorAll(".site-mobile-user-menu[open]").forEach(function (node) {
        node.removeAttribute("open");
      });
    });
  }

  function initCopyActions() {
    if (document.body.getAttribute("data-copy-actions-bound") === "1") return;
    document.body.setAttribute("data-copy-actions-bound", "1");
    document.addEventListener("click", function (event) {
      var copyBtn = event.target && event.target.closest ? event.target.closest("[data-copy-link]") : null;
      if (copyBtn) {
        event.preventDefault();
        var value = copyBtn.getAttribute("data-copy-text") || window.location.href;
        runtime().copyText(value)
          .then(function () {
            runtime().showToast(copyBtn.getAttribute("data-copy-success") || "Ссылка скопирована", "success");
          })
          .catch(function () {
            runtime().showToast("Не удалось скопировать ссылку", "danger");
          });
        return;
      }
      var selectable = event.target && event.target.closest ? event.target.closest("[data-copy-select]") : null;
      if (selectable && typeof selectable.select === "function") {
        selectable.select();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initFallbackImages();
    initCopyActions();
    initLiveSearchDismiss();
    initFilterDropdown();
    initDesktopHeaderMenus();
    initMobileHeaderMenu();
  });
})();
