(function () {
  var html = document.documentElement;

  // First visit picks system preference
  if (!localStorage.getItem('theme')) {
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      html.classList.add('light');
    }
  } else if (localStorage.getItem('theme') === 'light') {
    html.classList.add('light');
  }

  var btn = document.getElementById('theme-toggle');
  if (!btn) return;

  btn.textContent = html.classList.contains('light') ? 'Dark Mode' : 'Light Mode';

  btn.addEventListener('click', function () {
    var isLight = html.classList.toggle('light');
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
    btn.textContent = isLight ? 'Dark Mode' : 'Light Mode';
  });
})();
