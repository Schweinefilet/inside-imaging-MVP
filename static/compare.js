// Before/After Image Comparison Component
(function() {
  'use strict';

  function initCompare(container) {
    const wrapper = container.querySelector('.compare-wrapper, .compare-wrapper-compact');
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
      wrapper.classList.add('drag-active');
      wrapper.style.cursor = 'col-resize';
      const point = e.touches && e.touches.length ? e.touches[0].clientX : e.clientX;
      if (Number.isFinite(point)) {
        updatePosition(point);
      }
    }

    function handleEnd() {
      isDragging = false;
      wrapper.classList.remove('drag-active');
      wrapper.style.cursor = 'col-resize';
    }

    // Mouse events
    wrapper.addEventListener('mousedown', handleStart);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleEnd);

    // Touch events
    wrapper.addEventListener('touchstart', function(e) {
      handleStart(e);
    }, { passive: true });
    document.addEventListener('touchmove', handleTouchMove, { passive: false });
    document.addEventListener('touchend', handleEnd);

    // Mode detection
    const mode = container.dataset.mode || 'drag';
    
    // For hover mode only
    if (mode === 'hover') {
      wrapper.addEventListener('mousemove', function(e) {
        if (isDragging) return; // Don't interfere with drag
        const rect = wrapper.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));
        
        secondImage.style.clipPath = `inset(0 ${100 - percentage}% 0 0)`;
        slider.style.left = `${percentage}%`;
      });

      wrapper.addEventListener('mouseleave', function() {
        if (!isDragging) {
          // Reset to center on leave
          secondImage.style.clipPath = `inset(0 50% 0 0)`;
          slider.style.left = '50%';
        }
      });
    }

    requestAnimationFrame(function() {
      const rect = wrapper.getBoundingClientRect();
      if (rect.width > 0) {
        updatePosition(rect.left + rect.width / 2);
      }
    });
  }

  // Initialize all comparison containers
  document.addEventListener('DOMContentLoaded', function() {
    const containers = document.querySelectorAll('.compare-container, .compare-container-compact');
    containers.forEach(function(container) {
      initCompare(container);
    });
  });
})();
