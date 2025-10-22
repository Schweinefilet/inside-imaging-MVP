// static/loader.js - Spinning circle loader with consistent animation
// LoaderFive component - Generates report loading screen

(function () {
  'use strict';

  var DEFAULT_PRIMARY = "Generating your report...";
  var DEFAULT_SECONDARY = "This may take up to 30 seconds.";

  function ensureOverlay() {
    let el = document.getElementById('global-loader');
    if (el) {
      return el;
    }

    el = document.createElement('div');
    el.id = 'global-loader';
    el.className = 'loader-overlay loader-hidden';
    el.setAttribute('role', 'status');
    el.innerHTML = [
      '<div class="loader-card">',
      '  <div class="loader-one" aria-hidden="true">',
      '    <svg class="loader-one-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">',
      '      <circle class="loader-one-circle" cx="50" cy="50" r="45"/>',
      '    </svg>',
      '  </div>',
      '  <div class="loader-text" data-loader-text>' + DEFAULT_PRIMARY + '</div>',
      '  <div class="loader-sub" data-loader-sub>' + DEFAULT_SECONDARY + '</div>',
      '</div>'
    ].join('');

    document.body.appendChild(el);
    return el;
  }

  function show(text, subtext) {
    const overlay = ensureOverlay();
    const label = overlay.querySelector('[data-loader-text]');
    if (label) {
      label.textContent = text || DEFAULT_PRIMARY;
    }
    const subLabel = overlay.querySelector('[data-loader-sub]');
    if (subLabel) {
      subLabel.textContent = subtext || DEFAULT_SECONDARY;
    }
    overlay.classList.remove('loader-hidden');
  }

  function hide() {
    const overlay = ensureOverlay();
    overlay.classList.add('loader-hidden');
  }

  // Initialize on DOM ready
  document.addEventListener('DOMContentLoaded', function () {
    ensureOverlay();

    // Auto-show loader when upload form is submitted
    document.querySelectorAll('form[action$="/upload"]').forEach(function (form) {
      form.addEventListener('submit', function () {
        show("Generating your report...", "This may take up to 30 seconds.");
      }, { passive: true });
    });

    // Allow manual trigger via data attribute
    document.querySelectorAll('[data-show-loader]').forEach(function (el) {
      el.addEventListener('click', function () {
        show();
      }, { passive: true });
    });

    // Hide loader when page is shown (e.g., back button)
    window.addEventListener('pageshow', function () {
      hide();
    });
  });

  // Export LoaderFive API (React-style naming as requested)
  window.LoaderFive = {
    show: show,
    hide: hide,
    text: function(primaryText, secondaryText) {
      show(primaryText, secondaryText);
    }
  };

  // Also export as GlobalLoader for backward compatibility
  window.GlobalLoader = {
    show: show,
    hide: hide,
  };
})();

