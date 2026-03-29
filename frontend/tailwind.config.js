/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // ADIVA design tokens matching Figma
        brand: {
          DEFAULT: '#4F46E5',
          hover:   '#4338CA',
          light:   '#6366F1',
        },
        surface: {
          DEFAULT: '#1A1A2E',
          border:  '#2A2A3E',
          hover:   '#1F1F2E',
          deep:    '#0F0F1A',
        },
        status: {
          queued:        '#6B7280',
          processing:    '#3B82F6',
          completed:     '#10B981',
          needs_review:  '#F59E0B',
          low_confidence:'#F97316',
          failed:        '#EF4444',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-gentle': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow':    'spin 2s linear infinite',
      },
    },
  },
  plugins: [],
};
