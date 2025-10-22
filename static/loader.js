// static/loader.js - Enhanced LoaderFive-style component (vanilla JS)
// Mimics Aceternity LoaderFive aesthetic without React dependency

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
      '  <div class="loader-five-container" aria-hidden="true">',
      '    <!-- Multiple spinning rings for depth effect -->',
      '    <div class="loader-ring loader-ring-1"></div>',
      '    <div class="loader-ring loader-ring-2"></div>',
      '    <div class="loader-ring loader-ring-3"></div>',
      '    <div class="loader-core"></div>',
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

  // Export LoaderFive API (React-style naming)
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