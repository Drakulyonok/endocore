// Sticky language preference — the same UX pattern as the color-scheme
// toggle: pick once, it's remembered in localStorage, and every page load
// (any page, any entry point) is steered to match it. Piggybacks on the
// language-switcher links mkdocs-static-i18n already renders in the header
// (`.md-select__link[hreflang]`), so no separate routing/config is needed.
(function () {
  var STORAGE_KEY = "endocore-lang";

  function readStored() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  function remember(lang) {
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch (e) {
      /* localStorage unavailable (private mode, disabled) — degrade to no-op */
    }
  }

  function switcherLinks() {
    return document.querySelectorAll(".md-select__link[hreflang]");
  }

  // Remember an explicit choice the moment the visitor makes it.
  switcherLinks().forEach(function (link) {
    link.addEventListener("click", function () {
      remember(link.getAttribute("hreflang"));
    });
  });

  var stored = readStored();
  var preferred =
    stored || ((navigator.language || "en").slice(0, 2).toLowerCase() === "ru" ? "ru" : "en");
  var here = document.documentElement.lang || "en";

  if (preferred !== here) {
    var target = null;
    switcherLinks().forEach(function (link) {
      if (link.getAttribute("hreflang") === preferred) target = link.getAttribute("href");
    });
    // Landing on the target page flips `here` to `preferred`, so this can't loop.
    if (target) window.location.replace(target);
  }
})();
