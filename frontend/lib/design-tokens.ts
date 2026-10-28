// Obsidian proof ledger — single design-token source of truth.
//
// One dark theme. One action colour (YC orange #f26625). Emerald / amber /
// rose are reserved strictly for status semantics and are never used as
// decoration or action colours. Type scale: Bodoni Moda for hero/page
// titles only, Manrope for UI prose, JetBrains Mono for data/labels only.
export const TOKENS = {
  surface: {
    background: '#0a0a0f',
    secondary: '#12121a',
    tertiary: '#1a1a24',
    border: '#272738',
    borderSubtle: '#1c1c28',
  },
  action: {
    DEFAULT: '#f26625',
    hover: '#de581a',
    active: '#c94b11',
    light: '#ff7836',
    tint: 'rgba(242, 102, 37, 0.12)',
    border: 'rgba(242, 102, 37, 0.35)',
  },
  status: {
    ok: '#10b981',
    warn: '#f59e0b',
    bad: '#f43f5e',
    neutral: '#94a3b8',
  },
  text: {
    primary: '#f8fafc',
    muted: '#94a3b8',
  },
  font: {
    display: "'Bodoni Moda', serif",
    sans: "'Manrope', sans-serif",
    mono: "'JetBrains Mono', Menlo, monospace",
  },
  // Minimum size for meaningful text. Anything smaller is decoration only.
  minTextPx: 12,
} as const

export type StatusTone = 'ok' | 'warn' | 'bad' | 'neutral'
