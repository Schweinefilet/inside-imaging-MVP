/**
 * 3D Marquee - Aceternity-style with diagonal scrolling rows
 * Creates vertical-diagonal scrolling with perspective tilt
 */

(function() {
    'use strict';

    class Marquee3D {
        constructor(container, options = {}) {
            this.container = container;
            this.images = options.images || [];
            this.autoplay = options.autoplay !== false;
            this.numRows = 3; // 3 rows with better spacing
            
            this.init();
        }

        init() {
            if (this.images.length === 0) return;
            
            this.createStructure();
            this.attachEventListeners();
        }

        createStructure() {
            // Distribute images across rows to avoid duplicates appearing simultaneously
            const imagesPerRow = Math.max(4, Math.ceil(this.images.length / this.numRows));
            
            // Create a shuffled copy for variety
            const shuffledImages = [...this.images].sort(() => Math.random() - 0.5);
            
            // Create rows with unique image distribution
            let rowsHTML = '';
            for (let rowIndex = 0; rowIndex < this.numRows; rowIndex++) {
                let rowImages = [];
                
                // For 3 rows: distribute images to ensure rows 1 and 3 are different
                // Row 0: starts at position 0
                // Row 1: starts at position 1/3 through the array
                // Row 2: starts at position 2/3 through the array
                const baseOffset = Math.floor((rowIndex * this.images.length) / this.numRows);
                
                // Add additional offset for row 2 (3rd row) to differentiate from row 0
                const extraOffset = rowIndex === 2 ? Math.floor(this.images.length / 6) : 0;
                const offset = (baseOffset + extraOffset) % this.images.length;
                
                // Get unique images for this row by rotating through the array
                for (let i = 0; i < imagesPerRow; i++) {
                    const imageIndex = (offset + i) % this.images.length;
                    rowImages.push(this.images[imageIndex]);
                }
                
                // Duplicate exactly 2x - animation moves 50% so it loops perfectly
                const duplicatedImages = [...rowImages, ...rowImages];
                
                rowsHTML += `
                    <div class="marquee-3d-row" data-row="${rowIndex}">
                        ${duplicatedImages.map((img, i) => `
                            <div class="marquee-3d-item">
                                <img src="${img}" alt="Showcase ${i + 1}" loading="lazy">
                            </div>
                        `).join('')}
                    </div>
                `;
            }

            this.container.innerHTML = `
                <div class="marquee-3d-overlay">
                    <span class="marquee-kicker">Inside Imaging Studio</span>
                    <h1>Transform complex radiology reports into clear, actionable insights.</h1>
                    <p class="marquee-description">AI-powered translation, interactive body diagrams, and plain-language explanations that empower patients and streamline clinical communication.</p>
                    <div class="marquee-actions">
                        <a class="btn-primary" href="/dashboard">Try it now</a>
                        <a class="btn-secondary" href="#portfolio">View our projects</a>
                    </div>
                </div>
                <div class="marquee-3d-wrapper">
                    <div class="marquee-3d-scene">
                        ${rowsHTML}
                    </div>
                </div>
            `;

            this.rows = this.container.querySelectorAll('.marquee-3d-row');
            this.isPlaying = this.autoplay;
            
            // Ensure animations start immediately
            if (this.isPlaying) {
                this.rows.forEach(row => {
                    row.style.animationPlayState = 'running';
                });
            }
        }

        attachEventListeners() {
            // Scroll to center the marquee on page load
            this.scrollToCenter();
        }

        scrollToCenter() {
            // Smooth scroll to center the marquee in the viewport
            setTimeout(() => {
                const containerRect = this.container.getBoundingClientRect();
                const containerTop = containerRect.top + window.pageYOffset;
                const containerHeight = containerRect.height;
                const windowHeight = window.innerHeight;
                
                // Calculate scroll position to center the marquee
                const scrollTo = containerTop - (windowHeight / 2) + (containerHeight / 2);
                
                window.scrollTo({
                    top: scrollTo,
                    behavior: 'smooth'
                });
            }, 100);
        }
    }

    // Auto-initialize all marquee containers on page load
    function initMarquees() {
        const containers = document.querySelectorAll('[data-marquee-3d]');
        
        containers.forEach(container => {
            const imagesAttr = container.getAttribute('data-images');
            const images = imagesAttr ? JSON.parse(imagesAttr) : [];
            
            new Marquee3D(container, {
                images: images,
                autoplay: container.getAttribute('data-autoplay') !== 'false'
            });
        });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initMarquees);
    } else {
        initMarquees();
    }

    // Export for manual initialization
    window.Marquee3D = Marquee3D;
})();
