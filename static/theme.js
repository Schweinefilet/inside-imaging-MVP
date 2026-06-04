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
    syncMobileThemeLabel(dark);
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

  var MOON_SVG = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>';
  var SUN_SVG  = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>';

  function syncMobileThemeLabel(dark) {
    var lbl  = document.getElementById('mobile-theme-label');
    var icon = document.getElementById('mobile-theme-icon');
    // dark=true  → currently dark  → button offers "Light mode" → show sun
    // dark=false → currently light → button offers "Dark mode"  → show moon
    if (lbl)  lbl.textContent = dark ? 'Light mode' : 'Dark mode';
    if (icon) icon.innerHTML  = dark ? SUN_SVG : MOON_SVG;
  }

  function initMobileMenu() {
    var btn = document.getElementById('hamburger-btn');
    var nav = document.getElementById('mobile-nav');
    if (!btn || !nav) return;

    function openMenu() {
      nav.hidden = false;
      btn.setAttribute('aria-expanded', 'true');
      btn.setAttribute('aria-label', 'Close navigation menu');
    }

    function closeMenu() {
      nav.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
      btn.setAttribute('aria-label', 'Open navigation menu');
    }

    btn.addEventListener('click', function () {
      if (btn.getAttribute('aria-expanded') === 'true') {
        closeMenu();
      } else {
        openMenu();
      }
    });

    // Close on any link click inside the drawer
    nav.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', closeMenu);
    });

    // Mobile theme toggle button
    var mobileThemeBtn = document.getElementById('mobile-theme-btn');
    if (mobileThemeBtn) {
      mobileThemeBtn.addEventListener('click', function () {
        applyTheme(!isDark());
      });
    }

    // Close drawer when resizing to desktop
    window.addEventListener('resize', function () {
      if (window.innerWidth > 680) closeMenu();
    });
  }

  function init() {
    var dark = isDark();
    applyTheme(dark);
    syncMobileThemeLabel(dark);

    var toggle = document.getElementById('theme-toggle');
    if (toggle) {
      // toggle.checked = light, so dark = !toggle.checked
      toggle.addEventListener('change', function () {
        var nowDark = !toggle.checked;
        applyTheme(nowDark);
        syncMobileThemeLabel(nowDark);
      });
    }

    initUserMenu();
    initMobileMenu();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Re-sync on back/forward cache restore
  window.addEventListener('pageshow', function () { applyTheme(isDark()); });
})();
