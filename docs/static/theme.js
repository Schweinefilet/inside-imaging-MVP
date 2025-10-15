(function () {
  function setTheme(light) {
    document.documentElement.classList.toggle('light', !!light);
    localStorage.setItem('theme', light ? 'light' : 'dark');
    var cb = document.getElementById('theme-toggle');
    if (cb) cb.setAttribute('aria-checked', light ? 'true' : 'false');
    var lbl = document.getElementById('theme-label');
    if (lbl) lbl.textContent = light ? 'Light mode' : 'Dark mode';
  }

  document.addEventListener('DOMContentLoaded', function () {
    var cb = document.getElementById('theme-toggle');
    if (!cb) return;
    var saved = localStorage.getItem('theme');
    var isLight = saved ? saved === 'light'
      : (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches);
    cb.checked = isLight;
    setTheme(isLight);
    cb.addEventListener('change', function () { setTheme(cb.checked); }, { passive: true });
  });
})();
