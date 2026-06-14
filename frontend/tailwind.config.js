/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      colors: {
        // NITCC Design System — Dark Command Center Theme
        navy: {
          50:  '#e8eef7',
          100: '#c5d3ea',
          200: '#9fb5d8',
          300: '#7897c6',
          400: '#5c80b8',
          500: '#406aaa',
          600: '#355a93',
          700: '#264578',
          800: '#17305e',
          900: '#0A1628',  // Primary background
          950: '#06101a',
        },
        electric: {
          50:  '#e8f0fd',
          100: '#c5d8fa',
          200: '#9ebef7',
          300: '#77a4f3',
          400: '#5c90f0',
          500: '#1E6FD9',  // Primary accent
          600: '#1a60c0',
          700: '#154ea3',
          800: '#103e86',
          900: '#0a2d69',
        },
        critical: '#EF4444',   // Red — CRITICAL alerts
        warn: '#F59E0B',       // Amber — WARN alerts
        success: '#10B981',    // Emerald — healthy/OK
        info: '#3B82F6',       // Blue — INFO
        degraded: '#F97316',   // Orange — degraded
        watch: '#EAB308',      // Yellow — watch

        // Severity colors per PRD Appendix B
        severity: {
          critical: '#EF4444',
          high:     '#F97316',
          medium:   '#F59E0B',
          low:      '#3B82F6',
          info:     '#6B7280',
        },

        // Track health color coding (FR-03.1)
        health: {
          healthy:  '#10B981',  // Green  (80–100)
          watch:    '#EAB308',  // Yellow (60–79)
          degraded: '#F97316',  // Orange (30–59)
          critical: '#EF4444',  // Red    (0–29)
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-command': 'linear-gradient(135deg, #0A1628 0%, #0f1e35 50%, #0a1628 100%)',
        'gradient-card': 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
        'gradient-electric': 'linear-gradient(135deg, #1E6FD9 0%, #1a60c0 100%)',
        'gradient-danger': 'linear-gradient(135deg, #EF4444 0%, #dc2626 100%)',
      },
      boxShadow: {
        card: '0 4px 24px rgba(0, 0, 0, 0.4)',
        'card-hover': '0 8px 32px rgba(30, 111, 217, 0.2)',
        glow: '0 0 20px rgba(30, 111, 217, 0.3)',
        'glow-red': '0 0 20px rgba(239, 68, 68, 0.4)',
        'glow-amber': '0 0 20px rgba(245, 158, 11, 0.3)',
        'inner-glow': 'inset 0 1px 0 rgba(255,255,255,0.05)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'ping-slow': 'ping 2s cubic-bezier(0, 0, 0.2, 1) infinite',
        'blink': 'blink 1.5s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.3' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}
