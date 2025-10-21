(function () {
  function computeInitialLight() {
    var saved = localStorage.getItem('theme');
    if (saved === 'light') return true;
    if (saved === 'dark') return false;
    return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches);
  }

  function applyTheme(isLight) {
    var html  = document.documentElement;
    var toggle = document.getElementById('theme-toggle');
    var label  = document.getElementById('theme-label');

    html.classList.toggle('light', !!isLight);
    localStorage.setItem('theme', isLight ? 'light' : 'dark');

    if (toggle) {
      toggle.checked = !!isLight;
      toggle.setAttribute('aria-checked', isLight ? 'true' : 'false');
    }
    if (label) {
      label.textContent = isLight ? 'Light mode' : 'Dark mode';
    }
  }

  var initialLight = computeInitialLight();

  // Apply theme immediately to prevent flicker
  document.documentElement.classList.toggle('light', initialLight);

  document.addEventListener('DOMContentLoaded', function () {
    applyTheme(initialLight);

    var toggle = document.getElementById('theme-toggle');
    if (toggle) {
      toggle.addEventListener('change', function () {
        applyTheme(toggle.checked);
      }, { passive: true });
    }

    // Follow OS changes only if user hasn't chosen a theme yet
    if (!localStorage.getItem('theme') && window.matchMedia) {
      try {
        var mq = window.matchMedia('(prefers-color-scheme: light)');
        var onChange = function (e) { applyTheme(e.matches); };
        if (mq.addEventListener) mq.addEventListener('change', onChange);
        else if (mq.addListener) mq.addListener(onChange); // Safari <14
      } catch (_) {}
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
  });
})();
