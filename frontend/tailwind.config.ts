import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ['class'],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0a0a0f',
        'background-secondary': '#12121a',
        'background-tertiary': '#1a1a24',
        foreground: '#f8fafc',
        surface: {
          DEFAULT: '#12121a',
          card: '#161622',
          elevated: '#1a1a24',
          hover: '#222230',
        },
        border: '#272738',
        'border-subtle': '#1c1c28',
        'border-active': '#3b3b52',
        muted: {
          DEFAULT: '#161622',
          foreground: '#94a3b8',
        },
        primary: {
          DEFAULT: '#6366f1',
          hover: '#818cf8',
          muted: '#4f46e5',
          glow: 'rgba(99, 102, 241, 0.35)',
        },
        emerald: {
          DEFAULT: '#10b981',
          hover: '#34d399',
          muted: '#064e3b',
          glow: 'rgba(16, 185, 129, 0.35)',
        },
        accent: {
          DEFAULT: '#6366f1',
          hover: '#818cf8',
          muted: '#4f46e5',
        },
        success: '#10b981',
        warning: '#f59e0b',
        error: '#f43f5e',
        info: '#38bdf8',
        card: {
          DEFAULT: '#12121a',
          foreground: '#f8fafc',
        },
        popover: {
          DEFAULT: '#161622',
          foreground: '#f8fafc',
        },
      },
      borderRadius: {
        '4xl': '2rem',
        '3xl': '1.5rem',
        '2xl': '1rem',
        xl: '0.75rem',
        lg: '0.5rem',
        md: '0.375rem',
        sm: '0.25rem',
        xs: '0.125rem',
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
        display: ['Plus Jakarta Sans', 'sans-serif'],
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        pulse: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'slide-in': {
          from: { transform: 'translateY(-10px)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        shimmer: 'shimmer 2s infinite linear',
        pulse: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fade-in 0.2s ease-out',
        'slide-in': 'slide-in 0.2s ease-out',
      },
    },
  },
  plugins: [],
}

export default config
