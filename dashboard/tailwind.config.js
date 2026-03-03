/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        aether: {
          50: '#eef7ff',
          100: '#d9edff',
          200: '#bce0ff',
          300: '#8eccff',
          400: '#59afff',
          500: '#338cff',
          600: '#1a6bf5',
          700: '#1355e1',
          800: '#1645b6',
          900: '#183d8f',
          950: '#142757',
        },
        safety: {
          critical: '#ef4444',
          high: '#f97316',
          medium: '#eab308',
          low: '#22c55e',
          info: '#6b7280',
        },
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.4s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-20px)', opacity: '0', maxHeight: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1', maxHeight: '200px' },
        },
      },
    },
  },
  plugins: [],
};
