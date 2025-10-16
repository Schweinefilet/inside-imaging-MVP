// static/loader.js
(function () {
  function ensureOverlay() {
    let el = document.getElementById('global-loader');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'global-loader';
    el.className = 'loader-overlay loader-hidden';
    el.setAttribute('role','status');
    el.innerHTML =
      '<div class="loader-card">' +
        '<div class="loader-spin" aria-hidden="true"></div>' +
        '<div class="loader-col">' +
          '<div class="loader-text">Working on your report…</div>' +
          '<div class="loader-sub">This can take about 30 seconds</div>' +
        '</div>' +
      '</div>';
    document.body.appendChild(el);
    return el;
  }

  function show() { ensureOverlay().classList.remove('loader-hidden'); }
  function hide() { ensureOverlay().classList.add('loader-hidden'); }

  document.addEventListener('DOMContentLoaded', function () {
    ensureOverlay();

    // Show on submit of any form that posts to /upload
    document.querySelectorAll('form[action$="/upload"]').forEach(function (f) {
      f.addEventListener('submit', function () { show(); }, { passive: true });
    });

    // Optional: buttons/links can opt-in
    document.querySelectorAll('[data-show-loader]').forEach(function (el) {
      el.addEventListener('click', function () { show(); }, { passive: true });
    });

    // Hide after load completes (for SPA fragments, if used)
    window.addEventListener('pageshow', function () { hide(); });
  });
})();
