/* Inside Imaging — theme toggle.
 * Light is the default. Adds .dark class on <html> when user opts in.
 * Tokens (static/tokens.css) handle all the color swapping.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'theme';

  function isDark() {
    try { return localStorage.getItem(STORAGE_KEY) === 'dark'; }
    catch (e) { return false; }
  }

  function persist(theme) {
    try { localStorage.setItem(STORAGE_KEY, theme); }
    catch (e) { /* private mode: skip */ }
  }

  function applyTheme(dark) {
    var html = document.documentElement;
    html.classList.toggle('dark', !!dark);
    html.style.colorScheme = dark ? 'dark' : 'light';
    persist(dark ? 'dark' : 'light');
    syncUi(dark);
  }

  function syncUi(dark) {
    var toggle = document.getElementById('theme-toggle');
    var label  = document.getElementById('theme-label');
    if (toggle) {
      toggle.checked = !dark;  // checked = light (sun icon visible)
      toggle.setAttribute('aria-checked', dark ? 'false' : 'true');
    }
    if (label) label.textContent = dark ? 'Dark mode' : 'Light mode';
  }

  function initUserMenu() {
    document.querySelectorAll('.user-menu').forEach(function (menu) {
      var btn = menu.querySelector('.user-menu-toggle');
      var dd  = menu.querySelector('.user-menu-dropdown');
      if (!btn || !dd) return;

      function close() {
        btn.setAttribute('aria-expanded', 'false');
        dd.hidden = true;
        menu.classList.remove('open');
      }

      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var expanded = btn.getAttribute('aria-expanded') === 'true';
        if (expanded) {
          close();
        } else {
          dd.hidden = false;
          btn.setAttribute('aria-expanded', 'true');
          menu.classList.add('open');
        }
      });

      btn.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { close(); btn.focus(); }
        if (e.key === 'ArrowDown' && dd.hidden) {
          e.preventDefault();
          dd.hidden = false;
          btn.setAttribute('aria-expanded', 'true');
          menu.classList.add('open');
          var first = dd.querySelector('a');
          if (first) first.focus();
        }
      });

      dd.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { close(); btn.focus(); }
      });

      dd.querySelectorAll('a').forEach(function (link) {
        link.addEventListener('click', close);
      });

      document.addEventListener('click', function (e) {
        if (!menu.contains(e.target)) close();
      });
    });
  }

  function init() {
    applyTheme(isDark());

    var toggle = document.getElementById('theme-toggle');
    if (toggle) {
      // toggle.checked = light, so dark = !toggle.checked
      toggle.addEventListener('change', function () {
        applyTheme(!toggle.checked);
      });
    }

    initUserMenu();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Re-sync on back/forward cache restore
  window.addEventListener('pageshow', function () { applyTheme(isDark()); });
})();
