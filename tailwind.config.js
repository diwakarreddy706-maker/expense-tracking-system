/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './static/js/**/*.js',
    './apps/**/forms.py',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        agri: {
          bg: '#0B0F17',
          card: '#131A26',
          card2: '#182234',
          hover: '#1F2A3F',
          border: '#28354A',
          borderLight: '#374761',
          primary: '#10B981',
          primaryHover: '#059669',
          primaryLight: 'rgba(16, 185, 129, 0.15)',
          warning: '#F59E0B',
          warningLight: 'rgba(245, 158, 11, 0.15)',
          danger: '#EF4444',
          dangerLight: 'rgba(239, 68, 68, 0.15)',
          info: '#3B82F6',
          infoLight: 'rgba(59, 130, 246, 0.15)',
          purple: '#8B5CF6',
          purpleLight: 'rgba(139, 92, 246, 0.15)',
          text: '#F3F4F6',
          muted: '#9CA3AF',
          dim: '#6B7280',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Roboto Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'card': '0 4px 20px -2px rgba(0, 0, 0, 0.5)',
        'card-hover': '0 10px 25px -3px rgba(0, 0, 0, 0.6), 0 0 15px -3px rgba(16, 185, 129, 0.1)',
        'modal': '0 25px 50px -12px rgba(0, 0, 0, 0.8)',
      },
    },
  },
  plugins: [],
}
