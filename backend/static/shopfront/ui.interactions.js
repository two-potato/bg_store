(function () {
  function runtime() {
    return window.ServioRuntime || null;
  }

  function monitoring() {
    return window.ServioMonitoring || null;
  }

  function captureInteractionIssue(message, extra, error) {
    var monitor = monitoring();
    if (!monitor) return;
    if (error && typeof monitor.captureException === "function") {
      monitor.captureException(error, Object.assign({ kind: "shopfront_interaction" }, extra || {}));
      return;
    }
    if (typeof monitor.captureMessage === "function") {
      monitor.captureMessage(message, "warning", Object.assign({ kind: "shopfront_interaction" }, extra || {}));
    }
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

  function initCatalogAutocomplete() {
    if (document.body.getAttribute("data-catalog-autocomplete-bound") === "1") return;
    document.body.setAttribute("data-catalog-autocomplete-bound", "1");

    function closeMenu(widget) {
      var menu = widget.querySelector("[data-autocomplete-menu]");
      if (!menu) return;
      menu.innerHTML = "";
      menu.classList.add("hidden");
    }

    function closeAllMenus(exceptWidget) {
      document.querySelectorAll("[data-catalog-autocomplete]").forEach(function (widget) {
        if (exceptWidget && widget === exceptWidget) return;
        closeMenu(widget);
      });
    }

    function renderItems(widget, items) {
      var menu = widget.querySelector("[data-autocomplete-menu]");
      var input = widget.querySelector("[data-autocomplete-input]");
      var hiddenInput = widget.querySelector("[data-autocomplete-value]");
      if (!menu || !input || !hiddenInput) return;
      if (!items.length) {
        closeMenu(widget);
        return;
      }
      menu.innerHTML = "";
      items.forEach(function (item) {
        var option = document.createElement("button");
        option.type = "button";
        option.className = "catalog-autocomplete__option flex w-full items-start justify-between gap-3 rounded-xl px-3 py-2 text-left text-sm hover:bg-base-200";
        option.setAttribute("data-autocomplete-option", "1");
        option.setAttribute("data-value", item.value || "");
        option.setAttribute("data-label", item.label || "");

        var text = document.createElement("span");
        text.textContent = item.label || "";
        option.appendChild(text);

        if (item.hint) {
          var hint = document.createElement("span");
          hint.className = "text-xs text-base-content/60";
          hint.textContent = item.hint;
          option.appendChild(hint);
        }

        menu.appendChild(option);
      });
      menu.classList.remove("hidden");
    }

    function bindWidget(widget) {
      if (!widget || widget.getAttribute("data-autocomplete-bound") === "1") return;
      widget.setAttribute("data-autocomplete-bound", "1");
      var input = widget.querySelector("[data-autocomplete-input]");
      var hiddenInput = widget.querySelector("[data-autocomplete-value]");
      var endpoint = widget.getAttribute("data-endpoint") || "";
      var kind = widget.getAttribute("data-kind") || "";
      var debounceTimer = null;
      if (!input || !hiddenInput || !endpoint || !kind) return;

      input.addEventListener("input", function () {
        hiddenInput.value = "";
        closeMenu(widget);
        var query = (input.value || "").trim();
        if (query.length < 2) return;
        window.clearTimeout(debounceTimer);
        debounceTimer = window.setTimeout(function () {
          var url = new URL(endpoint, window.location.origin);
          url.searchParams.set("kind", kind);
          url.searchParams.set("q", query);
          fetch(url.toString(), {
            headers: {
              "Accept": "application/json",
              "X-Requested-With": "XMLHttpRequest"
            },
            credentials: "same-origin"
          })
            .then(function (response) {
              var contentType = String(response.headers.get("content-type") || "").toLowerCase();
              if (!response.ok) throw new Error("catalog_filter_suggestions_http_" + response.status);
              if (contentType.indexOf("application/json") < 0) throw new Error("catalog_filter_suggestions_content_type");
              return response.json();
            })
            .then(function (payload) {
              renderItems(widget, Array.isArray(payload.items) ? payload.items : []);
            })
            .catch(function (error) {
              captureInteractionIssue("catalog_filter_suggestions_failed", {
                kind: kind,
                endpoint: endpoint,
                query_length: query.length,
              }, error);
              closeMenu(widget);
            });
        }, 180);
      });

      input.addEventListener("focus", function () {
        if ((input.value || "").trim().length >= 2) {
          input.dispatchEvent(new Event("input", { bubbles: true }));
        }
      });
    }

    function bindWidgets(root) {
      var scope = root && root.querySelectorAll ? root : document;
      scope.querySelectorAll("[data-catalog-autocomplete]").forEach(bindWidget);
    }

    bindWidgets(document);

    document.addEventListener("click", function (event) {
      var option = event.target && event.target.closest ? event.target.closest("[data-autocomplete-option]") : null;
      if (option) {
        var widget = option.closest("[data-catalog-autocomplete]");
        if (!widget) return;
        var input = widget.querySelector("[data-autocomplete-input]");
        var hiddenInput = widget.querySelector("[data-autocomplete-value]");
        if (!input || !hiddenInput) return;
        hiddenInput.value = option.getAttribute("data-value") || "";
        input.value = option.getAttribute("data-label") || "";
        closeMenu(widget);
        return;
      }

      var insideWidget = event.target && event.target.closest ? event.target.closest("[data-catalog-autocomplete]") : null;
      closeAllMenus(insideWidget);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      closeAllMenus();
    });

    document.body.addEventListener("htmx:afterSettle", function (event) {
      bindWidgets(event.target || document);
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
            runtime().showToast("Не удалось скопировать ссылку", "warning");
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
    initCatalogAutocomplete();
    initDesktopHeaderMenus();
    initMobileHeaderMenu();
  });
})();
