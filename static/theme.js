(function () {
  var transitionTimer = null;
  var initialized = false;

  /* ── Full variable palette for each mode ── */
  var DARK = {
    bg:'#09090b', panel:'#18191f', 'panel-2':'#22242d',
    text:'#f2f6f4', muted:'#8a8f95', border:'#32353f',
    mint:'#3ee6b0', shadow:'0 18px 45px rgba(0,0,0,0.55)',
    'card-bg':'rgba(255,255,255,0.02)',
    'border-color':'rgba(255,255,255,0.1)',
    'text-primary':'#f2f6f4', 'text-muted':'#8a8f95'
  };
  var LIGHT = {
    bg:'#f8f9fa', panel:'#ffffff', 'panel-2':'#eef2f7',
    text:'#1f2937', muted:'#4b5563', border:'#d7dde5',
    mint:'#0fb989', shadow:'0 4px 10px rgba(0,0,0,.08)',
    'card-bg':'#ffffff', 'border-color':'#d7dde5',
    'text-primary':'#1f2937', 'text-muted':'#4b5563'
  };

  function computeInitialLight() {
    var saved = localStorage.getItem('theme');
    return saved === 'light';
  }

  function syncThemeUi(isLight) {
    var toggle = document.getElementById('theme-toggle');
    var label = document.getElementById('theme-label');

    if (toggle) {
      toggle.checked = !!isLight;
      toggle.setAttribute('aria-checked', isLight ? 'true' : 'false');
    }
    if (label) {
      label.textContent = isLight ? 'Light mode' : 'Dark mode';
    }
  }

  function applyRootPaintHints(html, isLight) {
    var vars = isLight ? LIGHT : DARK;
    html.style.colorScheme = isLight ? 'light' : 'dark';
    html.style.backgroundColor = vars.bg;
    for (var k in vars) {
      if (vars.hasOwnProperty(k)) html.style.setProperty('--' + k, vars[k]);
    }
  }

  function clearThemeTransitionClasses(html) {
    html.classList.remove('theme-transitioning', 'to-light', 'to-dark');
  }

  function applyTheme(isLight, skipTransition) {
    var html = document.documentElement;
    var nextIsLight = !!isLight;
    var currentIsLight = html.classList.contains('light');

    if (transitionTimer) {
      clearTimeout(transitionTimer);
      transitionTimer = null;
    }

    if (skipTransition || currentIsLight === nextIsLight) {
      clearThemeTransitionClasses(html);
      html.classList.toggle('light', nextIsLight);
      applyRootPaintHints(html, nextIsLight);
      localStorage.setItem('theme', nextIsLight ? 'light' : 'dark');
      syncThemeUi(nextIsLight);
      return;
    }

    clearThemeTransitionClasses(html);
    html.classList.add('theme-transitioning', nextIsLight ? 'to-light' : 'to-dark');
    html.classList.toggle('light', nextIsLight);
    applyRootPaintHints(html, nextIsLight);
    localStorage.setItem('theme', nextIsLight ? 'light' : 'dark');
    syncThemeUi(nextIsLight);

    transitionTimer = setTimeout(function () {
      clearThemeTransitionClasses(html);
      transitionTimer = null;
    }, 500);
  }

  var initialLight = computeInitialLight();
  document.documentElement.classList.toggle('light', initialLight);
  applyRootPaintHints(document.documentElement, initialLight);

  function initThemeUi() {
    if (initialized) return;
    initialized = true;

    var p = document.getElementById('prepaint-bg');
    if (p) p.remove();

    applyTheme(computeInitialLight(), true);

    var toggle = document.getElementById('theme-toggle');
    if (toggle) {
      toggle.addEventListener('change', function () {
        applyTheme(toggle.checked, false);
      });
    }

    document.querySelectorAll('.user-menu').forEach(function (menu) {
      var toggleBtn = menu.querySelector('.user-menu-toggle');
      var dropdown = menu.querySelector('.user-menu-dropdown');
      if (!toggleBtn || !dropdown) return;

      var closeMenu = function () {
        toggleBtn.setAttribute('aria-expanded', 'false');
        dropdown.hidden = true;
        menu.classList.remove('open');
      };

      toggleBtn.addEventListener('click', function (event) {
        event.preventDefault();
        var expanded = toggleBtn.getAttribute('aria-expanded') === 'true';
        if (expanded) {
          closeMenu();
        } else {
          dropdown.hidden = false;
          toggleBtn.setAttribute('aria-expanded', 'true');
          menu.classList.add('open');
        }
      });

      toggleBtn.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
          closeMenu();
          toggleBtn.focus();
        }
        if (event.key === 'ArrowDown' && dropdown.hidden) {
          event.preventDefault();
          dropdown.hidden = false;
          toggleBtn.setAttribute('aria-expanded', 'true');
          menu.classList.add('open');
          var firstLink = dropdown.querySelector('a');
          if (firstLink) firstLink.focus();
        }
      });

      dropdown.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
          closeMenu();
          toggleBtn.focus();
        }
      });

      dropdown.querySelectorAll('a').forEach(function (link) {
        link.addEventListener('click', closeMenu);
      });

      document.addEventListener('click', function (event) {
        if (!menu.contains(event.target)) {
          closeMenu();
        }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initThemeUi);
  } else {
    initThemeUi();
  }

  window.addEventListener('pageshow', function () {
    applyTheme(computeInitialLight(), true);
  });
})();
