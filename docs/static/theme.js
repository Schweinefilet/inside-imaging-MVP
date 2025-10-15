(function () {
  function setTheme(light) {
    document.documentElement.classList.toggle('light', !!light);
    localStorage.setItem('theme', light ? 'light' : 'dark');
    var btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.setAttribute('aria-pressed', light ? 'true' : 'false');
      btn.textContent = light ? '☀️' : '🌙';
      btn.title = light ? 'Switch to dark' : 'Switch to light';
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    var saved = localStorage.getItem('theme');
    var isLight = saved ? saved === 'light'
      : (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches);
    setTheme(isLight);
    btn.addEventListener('click', function () {
      setTheme(!document.documentElement.classList.contains('light'));
    }, { passive: true });
  });
})();
