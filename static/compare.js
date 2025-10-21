// Before/After Image Comparison Component
(function() {
  'use strict';

  function initCompare(container) {
    const wrapper = container.querySelector('.compare-wrapper');
    const secondImage = container.querySelector('.compare-image.second');
    const slider = container.querySelector('.compare-slider');
    const handle = container.querySelector('.compare-handle');
    
    if (!wrapper || !secondImage || !slider || !handle) return;

    let isDragging = false;
    let currentPosition = 50; // percentage

    function updatePosition(clientX) {
      const rect = wrapper.getBoundingClientRect();
      const x = clientX - rect.left;
      const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));
      
      currentPosition = percentage;
      secondImage.style.clipPath = `inset(0 ${100 - percentage}% 0 0)`;
      slider.style.left = `${percentage}%`;
    }

    function handleMouseMove(e) {
      if (!isDragging) return;
      e.preventDefault();
      updatePosition(e.clientX);
    }

    function handleTouchMove(e) {
      if (!isDragging) return;
      e.preventDefault();
      if (e.touches && e.touches.length > 0) {
        updatePosition(e.touches[0].clientX);
      }
    }

    function handleStart(e) {
      isDragging = true;
      wrapper.style.cursor = 'col-resize';
    }

    function handleEnd() {
      isDragging = false;
      wrapper.style.cursor = 'col-resize';
    }

    // Mouse events
    wrapper.addEventListener('mousedown', handleStart);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleEnd);

    // Touch events
    wrapper.addEventListener('touchstart', handleStart, { passive: true });
    document.addEventListener('touchmove', handleTouchMove, { passive: false });
    document.addEventListener('touchend', handleEnd);

    // Hover mode - follow mouse without clicking
    const mode = container.dataset.mode || 'drag';
    if (mode === 'hover') {
      wrapper.addEventListener('mousemove', function(e) {
        const rect = wrapper.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));
        
        secondImage.style.clipPath = `inset(0 ${100 - percentage}% 0 0)`;
        slider.style.left = `${percentage}%`;
      });

      wrapper.addEventListener('mouseleave', function() {
        // Reset to center on leave
        secondImage.style.clipPath = `inset(0 50% 0 0)`;
        slider.style.left = '50%';
      });
    }
  }

  // Initialize all comparison containers
  document.addEventListener('DOMContentLoaded', function() {
    const containers = document.querySelectorAll('.compare-container');
    containers.forEach(function(container) {
      initCompare(container);
    });
  });
})();
