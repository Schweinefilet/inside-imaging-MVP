// charts.js - Interactive charts for statistics page
(function() {
  'use strict';

  let globalTooltip = null;

  function ensureTooltip() {
    if (globalTooltip && document.body.contains(globalTooltip)) {
      return globalTooltip;
    }
    globalTooltip = document.createElement('div');
    globalTooltip.className = 'chart-tooltip';
    globalTooltip.setAttribute('role', 'status');
    globalTooltip.setAttribute('aria-live', 'polite');
    document.body.appendChild(globalTooltip);
    return globalTooltip;
  }

  function hideTooltip() {
    if (!globalTooltip) return;
    globalTooltip.style.display = 'none';
  }

  // Simple line chart for time-series data with dates
  function createLineChart(canvas, data, label) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const padding = 40;
    const chartWidth = width - 2 * padding;
    const chartHeight = height - 2 * padding;

    // Find min and max
    const values = data.map(d => d.value);
    const max = Math.max(...values, 1);
    const min = 0;
    const range = max - min || 1;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Draw axes
    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--border') || '#2a2f3a';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.stroke();

    // Draw Y-axis labels
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--muted') || '#7a8b9a';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    const ySteps = 3;
    for (let i = 0; i <= ySteps; i++) {
      const val = Math.round(min + (range * i / ySteps));
      const y = height - padding - (chartHeight * i / ySteps);
      ctx.fillText(val.toString(), padding - 5, y + 3);
    }

    // Draw X-axis labels (dates)
    ctx.textAlign = 'center';
    const xLabelCount = Math.min(5, data.length);
    for (let i = 0; i < xLabelCount; i++) {
      const idx = Math.floor(i * (data.length - 1) / (xLabelCount - 1));
      const x = padding + (idx / (data.length - 1)) * chartWidth;
      ctx.fillText(data[idx].label, x, height - padding + 15);
    }

    // Draw smooth line (no nodes visible)
    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--mint') || '#22c55e';
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();

    data.forEach((point, i) => {
      const x = padding + (i / (data.length - 1)) * chartWidth;
      const y = height - padding - ((point.value - min) / range) * chartHeight;
      
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        // Use quadratic curves for smoothing
        if (i < data.length - 1) {
          const nextPoint = data[i + 1];
          const nextX = padding + ((i + 1) / (data.length - 1)) * chartWidth;
          const nextY = height - padding - ((nextPoint.value - min) / range) * chartHeight;
          const cpX = (x + nextX) / 2;
          const cpY = (y + nextY) / 2;
          ctx.quadraticCurveTo(x, y, cpX, cpY);
        } else {
          ctx.lineTo(x, y);
        }
      }
    });
    ctx.stroke();

    // Store data for hover interaction
    canvas._chartData = { data, padding, chartWidth, chartHeight, min, range, width, height };
  }

  // Simple pie chart with custom tooltip
  function createPieChart(canvas, data, colors) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) / 2 - 20;

    const total = data.reduce((sum, d) => sum + d.value, 0);
    if (total === 0) return; // Don't draw if no data

    let currentAngle = -Math.PI / 2;

    ctx.clearRect(0, 0, width, height);

    // Draw slices
    data.forEach((item, i) => {
      const sliceAngle = (item.value / total) * 2 * Math.PI;
      
      ctx.fillStyle = colors[i % colors.length];
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.arc(centerX, centerY, radius, currentAngle, currentAngle + sliceAngle);
      ctx.closePath();
      ctx.fill();

      // Add stroke
      ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--bg') || '#0b0c0f';
      ctx.lineWidth = 2;
      ctx.stroke();

      currentAngle += sliceAngle;
    });

    const tooltip = ensureTooltip();

    // Add hover interaction with custom tooltip
    canvas.addEventListener('mousemove', function(e) {
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const dx = x - centerX;
      const dy = y - centerY;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist <= radius) {
        let angle = Math.atan2(dy, dx);
        if (angle < -Math.PI / 2) angle += 2 * Math.PI;
        angle += Math.PI / 2;
        if (angle < 0) angle += 2 * Math.PI;

        let accAngle = 0;
        let foundIndex = -1;

        data.forEach((item, i) => {
          const sliceAngle = (item.value / total) * 2 * Math.PI;
          if (angle >= accAngle && angle < accAngle + sliceAngle) {
            foundIndex = i;
          }
          accAngle += sliceAngle;
        });

        if (foundIndex >= 0) {
          canvas.style.cursor = 'pointer';
          const percent = ((data[foundIndex].value / total) * 100).toFixed(1);
          tooltip.textContent = `${data[foundIndex].label}: ${data[foundIndex].value} (${percent}%)`;
          tooltip.style.display = 'block';
          
          // Position tooltip following cursor with bounds checking
          const tooltipRect = tooltip.getBoundingClientRect();
          let left = e.clientX + 16;
          let top = e.clientY - (tooltipRect.height / 2) - 4;
          
          // Keep tooltip within viewport
          if (left + tooltipRect.width > window.innerWidth) {
            left = e.clientX - tooltipRect.width - 16;
          }
          if (left < 8) {
            left = 8;
          }
          if (top < 8) {
            top = 8;
          }
          if (top + tooltipRect.height > window.innerHeight - 8) {
            top = window.innerHeight - tooltipRect.height - 8;
          }
          
          tooltip.style.left = left + 'px';
          tooltip.style.top = top + 'px';
        } else {
          canvas.style.cursor = 'default';
          hideTooltip();
        }
      } else {
        canvas.style.cursor = 'default';
        hideTooltip();
      }
    });

    canvas.addEventListener('mouseleave', function() {
      hideTooltip();
    });
  }

  // Initialize charts when DOM is ready
  document.addEventListener('DOMContentLoaded', function() {
    // Line chart for reports over time (use real data if available)
    const lineCanvas = document.getElementById('line-chart-reports');
    if (lineCanvas) {
      let timeSeriesData = [];
      
      if (window.statsData && window.statsData.reportsTimeSeries) {
        // Use actual data from backend
        timeSeriesData = window.statsData.reportsTimeSeries;
      } else {
        // Fallback: generate last 30 days with zero values
        for (let i = 29; i >= 0; i--) {
          const date = new Date();
          date.setDate(date.getDate() - i);
          const monthDay = (date.getMonth() + 1) + '/' + date.getDate();
          timeSeriesData.push({
            label: monthDay,
            value: 0
          });
        }
      }
      
      createLineChart(lineCanvas, timeSeriesData, 'Reports');
    }

    // Pie chart for age distribution
    const ageCanvas = document.getElementById('pie-chart-age');
    if (ageCanvas && window.statsData && window.statsData.ageData) {
      const colors = ['#22c55e', '#10b981', '#059669', '#047857', '#065f46'];
      createPieChart(ageCanvas, window.statsData.ageData, colors);
    }

    // Pie chart for gender mix
    const genderCanvas = document.getElementById('pie-chart-gender');
    if (genderCanvas && window.statsData && window.statsData.genderData) {
      const colors = ['#ec4899', '#3b82f6', '#8b5cf6'];
      createPieChart(genderCanvas, window.statsData.genderData, colors);
    }

    // Pie chart for languages
    const langCanvas = document.getElementById('pie-chart-languages');
    if (langCanvas && window.statsData && window.statsData.languagesData) {
      const colors = ['#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];
      createPieChart(langCanvas, window.statsData.languagesData, colors);
    }

    // Pie chart for modalities
    const modalityCanvas = document.getElementById('pie-chart-modalities');
    if (modalityCanvas && window.statsData && window.statsData.modalitiesData) {
      const colors = ['#22c55e', '#10b981', '#059669', '#047857', '#065f46', '#064e3b', '#0c4a3e'];
      createPieChart(modalityCanvas, window.statsData.modalitiesData, colors);
    }

    // Pie chart for findings
    const findingsCanvas = document.getElementById('pie-chart-findings');
    if (findingsCanvas && window.statsData && window.statsData.findingsData) {
      const colors = ['#22c55e', '#f59e0b', '#ef4444', '#8b5cf6'];
      createPieChart(findingsCanvas, window.statsData.findingsData, colors);
    }
  });

  // Re-render charts on theme change
  window.addEventListener('storage', function(e) {
    if (e.key === 'theme') {
      setTimeout(function() {
        document.querySelectorAll('canvas').forEach(canvas => {
          const event = new Event('DOMContentLoaded');
          document.dispatchEvent(event);
        });
        hideTooltip();
      }, 50);
    }
  });
})();
