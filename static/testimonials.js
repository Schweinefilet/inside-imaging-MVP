// Animated Testimonials Component
(function() {
  'use strict';

  function initTestimonials() {
    const container = document.querySelector('.testimonials-container');
    if (!container) return;

    const cards = container.querySelectorAll('.testimonial-card');
    const dots = document.querySelectorAll('.testimonial-dot');
    const prevBtn = document.querySelector('.testimonial-nav-btn.prev');
    const nextBtn = document.querySelector('.testimonial-nav-btn.next');

    if (cards.length === 0) return;

    let currentIndex = 0;
    let autoplayInterval;

    function showTestimonial(index) {
      // Remove all active/prev classes
      cards.forEach((card, i) => {
        card.classList.remove('active', 'prev');
        if (i < index) {
          card.classList.add('prev');
        }
      });

      // Add active to current
      cards[index].classList.add('active');

      // Update dots
      dots.forEach((dot, i) => {
        dot.classList.toggle('active', i === index);
      });

      currentIndex = index;
    }

    function nextTestimonial() {
      const next = (currentIndex + 1) % cards.length;
      showTestimonial(next);
    }

    function prevTestimonial() {
      const prev = (currentIndex - 1 + cards.length) % cards.length;
      showTestimonial(prev);
    }

    function startAutoplay() {
      stopAutoplay();
      autoplayInterval = setInterval(nextTestimonial, 6000);
    }

    function stopAutoplay() {
      if (autoplayInterval) {
        clearInterval(autoplayInterval);
      }
    }

    // Event listeners
    if (prevBtn) {
      prevBtn.addEventListener('click', function() {
        prevTestimonial();
        stopAutoplay();
        startAutoplay();
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', function() {
        nextTestimonial();
        stopAutoplay();
        startAutoplay();
      });
    }

    dots.forEach((dot, index) => {
      dot.addEventListener('click', function() {
        showTestimonial(index);
        stopAutoplay();
        startAutoplay();
      });
    });

    // Pause on hover
    container.addEventListener('mouseenter', stopAutoplay);
    container.addEventListener('mouseleave', startAutoplay);

    // Keyboard navigation
    document.addEventListener('keydown', function(e) {
      if (e.key === 'ArrowLeft') {
        prevTestimonial();
        stopAutoplay();
        startAutoplay();
      } else if (e.key === 'ArrowRight') {
        nextTestimonial();
        stopAutoplay();
        startAutoplay();
      }
    });

    // Touch swipe support
    let touchStartX = 0;
    let touchEndX = 0;

    container.addEventListener('touchstart', function(e) {
      touchStartX = e.changedTouches[0].screenX;
      stopAutoplay();
    }, { passive: true });

    container.addEventListener('touchend', function(e) {
      touchEndX = e.changedTouches[0].screenX;
      handleSwipe();
      startAutoplay();
    }, { passive: true });

    function handleSwipe() {
      const swipeThreshold = 50;
      const diff = touchStartX - touchEndX;

      if (Math.abs(diff) > swipeThreshold) {
        if (diff > 0) {
          nextTestimonial();
        } else {
          prevTestimonial();
        }
      }
    }

    // Initialize
    showTestimonial(0);
    startAutoplay();
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTestimonials);
  } else {
    initTestimonials();
  }
})();
