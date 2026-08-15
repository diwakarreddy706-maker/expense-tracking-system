/**
 * EXPENSE TRACKING & MANAGEMENT SYSTEM - CHART.JS FOUNDATION HELPER
 */

window.DashboardCharts = {
  themeDefaults: {
    fontFamily: "'Inter', sans-serif",
    color: '#8B949E',
    gridColor: 'rgba(48, 54, 61, 0.5)',
  },

  initPlaceholderCharts: function() {
    // Phase 1 Chart framework initialization helper
    if (typeof Chart === 'undefined') return;

    Chart.defaults.font.family = this.themeDefaults.fontFamily;
    Chart.defaults.color = this.themeDefaults.color;
  }
};

document.addEventListener('DOMContentLoaded', () => {
  window.DashboardCharts.initPlaceholderCharts();
});
