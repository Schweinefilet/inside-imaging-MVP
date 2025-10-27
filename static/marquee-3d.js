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
            this.numRows = 4; // 4 rows for better coverage
            
            this.init();
        }

        init() {
            if (this.images.length === 0) return;
            
            this.createStructure();
            this.attachEventListeners();
        }

        createStructure() {
            // Distribute images across rows - duplicate exactly 2x for perfect 50% loop
            const imagesPerRow = Math.max(4, Math.ceil(this.images.length / this.numRows));
            
            // Create rows
            let rowsHTML = '';
            for (let rowIndex = 0; rowIndex < this.numRows; rowIndex++) {
                const startIdx = (rowIndex * imagesPerRow) % this.images.length;
                let rowImages = [];
                
                // Get images for this row
                for (let i = 0; i < imagesPerRow; i++) {
                    rowImages.push(this.images[(startIdx + i) % this.images.length]);
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
                <div class="marquee-3d-controls">
                    <button class="marquee-3d-toggle" aria-label="Pause animation">
                        Pause Animation
                    </button>
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
            const toggleBtn = this.container.querySelector('.marquee-3d-toggle');

            toggleBtn?.addEventListener('click', () => this.toggle());

            // No pause on hover - let it run continuously
        }

        toggle() {
            if (this.isPlaying) {
                this.pause();
            } else {
                this.play();
            }
        }

        play() {
            this.isPlaying = true;
            this.rows.forEach(row => {
                row.style.animationPlayState = 'running';
            });
            this.updateToggleButton();
        }

        pause() {
            this.isPlaying = false;
            this.rows.forEach(row => {
                row.style.animationPlayState = 'paused';
            });
            this.updateToggleButton();
        }

        updateToggleButton() {
            const toggleBtn = this.container.querySelector('.marquee-3d-toggle');
            if (toggleBtn) {
                toggleBtn.textContent = this.isPlaying ? 'Pause Animation' : 'Resume Animation';
                toggleBtn.setAttribute('aria-label', this.isPlaying ? 'Pause animation' : 'Resume animation');
            }
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
