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
  });
})();
