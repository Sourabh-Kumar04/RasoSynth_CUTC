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
        // Jet Black Palette (Pure Deep Space Obsidian)
        background: '#050508',
        'background-secondary': '#090a0f',
        'background-tertiary': '#0f111a',
        foreground: '#f4f6fa',
        surface: {
          DEFAULT: '#090a0f',
          card: '#0c0d14',
          elevated: '#12141e',
          hover: '#181b28',
        },
        border: '#1e2235',
        'border-subtle': '#141622',
        'border-active': '#008ecc',
        muted: {
          DEFAULT: '#0c0d14',
          foreground: '#8b949e',
        },
        // Cerulean Blue Palette
        cerulean: {
          DEFAULT: '#008ecc',
          hover: '#00a4eb',
          muted: '#006694',
          glow: 'rgba(0, 142, 204, 0.45)',
          tint: 'rgba(0, 142, 204, 0.12)',
          border: 'rgba(0, 142, 204, 0.35)',
        },
        // Neon Red Palette
        neon: {
          DEFAULT: '#ff0038',
          hover: '#ff2654',
          muted: '#990022',
          glow: 'rgba(255, 0, 56, 0.55)',
          tint: 'rgba(255, 0, 56, 0.12)',
          border: 'rgba(255, 0, 56, 0.35)',
        },
        primary: {
          DEFAULT: '#008ecc',
          hover: '#00a4eb',
          muted: '#006694',
          glow: 'rgba(0, 142, 204, 0.45)',
        },
        emerald: {
          DEFAULT: '#10b981',
          hover: '#34d399',
          muted: '#064e3b',
          glow: 'rgba(16, 185, 129, 0.35)',
        },
        accent: {
          DEFAULT: '#008ecc',
          hover: '#00a4eb',
          muted: '#006694',
        },
        yc: {
          DEFAULT: '#008ecc',
          hover: '#00a4eb',
          active: '#006694',
          light: '#38bdf8',
          tint: 'rgba(0, 142, 204, 0.12)',
          border: 'rgba(0, 142, 204, 0.35)',
        },
        success: '#10b981',
        warning: '#f59e0b',
        error: '#ff0038',
        info: '#008ecc',
        card: {
          DEFAULT: '#0c0d14',
          foreground: '#f4f6fa',
        },
        popover: {
          DEFAULT: '#0c0d14',
          foreground: '#f4f6fa',
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
