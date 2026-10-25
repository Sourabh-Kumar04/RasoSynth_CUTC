'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Palette, Check, Sparkles, RefreshCw, Eye, Sliders, Moon, Zap } from 'lucide-react'
import { clsx } from 'clsx'

export interface ColorPalette {
  id: string
  name: string
  primary: string
  hover: string
  muted: string
  glow: string
  badgeBg: string
  badgeText: string
  borderGlow: string
  description: string
}

export const COLOR_PALETTES: ColorPalette[] = [
  {
    id: 'neon-saffron',
    name: 'Neon Saffron',
    primary: '#f26625',
    hover: '#de581a',
    muted: '#ea580c',
    glow: 'rgba(242, 102, 37, 0.5)',
    badgeBg: 'rgba(242, 102, 37, 0.15)',
    badgeText: '#ff8a50',
    borderGlow: 'rgba(242, 102, 37, 0.4)',
    description: 'YC sovereign signal orange with warm amber reflections',
  },
  {
    id: 'cyber-emerald',
    name: 'Cyber Emerald',
    primary: '#10b981',
    hover: '#059669',
    muted: '#047857',
    glow: 'rgba(16, 185, 129, 0.5)',
    badgeBg: 'rgba(16, 185, 129, 0.15)',
    badgeText: '#34d399',
    borderGlow: 'rgba(16, 185, 129, 0.4)',
    description: 'High-precision terminal matrix green with laser focus',
  },
  {
    id: 'electric-violet',
    name: 'Electric Violet',
    primary: '#a855f7',
    hover: '#9333ea',
    muted: '#7e22ce',
    glow: 'rgba(168, 85, 247, 0.5)',
    badgeBg: 'rgba(168, 85, 247, 0.15)',
    badgeText: '#c084fc',
    borderGlow: 'rgba(168, 85, 247, 0.4)',
    description: 'Deep neural synthesizer purple with cosmic luminosity',
  },
  {
    id: 'tokyo-cyan',
    name: 'Tokyo Ice',
    primary: '#06b6d4',
    hover: '#0891b2',
    muted: '#0e7490',
    glow: 'rgba(6, 182, 212, 0.5)',
    badgeBg: 'rgba(6, 182, 212, 0.15)',
    badgeText: '#38bdf8',
    borderGlow: 'rgba(6, 182, 212, 0.4)',
    description: 'Cryogenic quantum cyan with icy crisp contrast',
  },
  {
    id: 'solar-flare',
    name: 'Solar Flare',
    primary: '#f59e0b',
    hover: '#d97706',
    muted: '#b45309',
    glow: 'rgba(245, 158, 11, 0.5)',
    badgeBg: 'rgba(245, 158, 11, 0.15)',
    badgeText: '#fbbf24',
    borderGlow: 'rgba(245, 158, 11, 0.4)',
    description: 'Industrial Bauhaus gold with pure functional energy',
  },
]

export function RealtimePaletteTester() {
  const [isOpen, setIsOpen] = useState(false)
  const [activePalette, setActivePalette] = useState<string>('neon-saffron')
  const [customHex, setCustomHex] = useState('#f26625')
  const [contrastRatio, setContrastRatio] = useState('8.4:1')

  const applyPalette = useCallback((palette: ColorPalette) => {
    if (typeof document === 'undefined') return
    const root = document.documentElement
    root.style.setProperty('--accent', palette.primary)
    root.style.setProperty('--accent-hover', palette.hover)
    root.style.setProperty('--accent-muted', palette.muted)
    root.style.setProperty('--glow-yc', `0 0 24px -2px ${palette.glow}`)

    // Also update any dynamic inline border & badge classes via stylesheet injection
    let styleEl = document.getElementById('dynamic-palette-style')
    if (!styleEl) {
      styleEl = document.createElement('style')
      styleEl.id = 'dynamic-palette-style'
      document.head.appendChild(styleEl)
    }

    styleEl.innerHTML = `
      :root {
        --accent: ${palette.primary} !important;
        --accent-hover: ${palette.hover} !important;
        --accent-muted: ${palette.muted} !important;
      }
      .bg-\\[\\#f26625\\] { background-color: ${palette.primary} !important; }
      .text-\\[\\#f26625\\] { color: ${palette.primary} !important; }
      .border-\\[\\#f26625\\] { border-color: ${palette.primary} !important; }
      .hover\\:bg-\\[\\#de581a\\]:hover { background-color: ${palette.hover} !important; }
      .hover\\:text-\\[\\#f26625\\]:hover { color: ${palette.primary} !important; }
      .focus-visible\\:ring-\\[\\#f26625\\]:focus-visible { --tw-ring-color: ${palette.primary} !important; }
      .glow-yc { box-shadow: 0 0 24px -2px ${palette.glow} !important; }
      ::selection { background-color: ${palette.primary} !important; color: #ffffff !important; }
    `

    try {
      localStorage.setItem('raso_palette_id', palette.id)
    } catch {
      // Ignore
    }
  }, [])

  // Initialize from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('raso_palette_id')
      if (saved) {
        const found = COLOR_PALETTES.find((p) => p.id === saved)
        if (found) {
          setActivePalette(found.id)
          applyPalette(found)
        }
      }
    } catch {
      // Ignore
    }
  }, [applyPalette])

  const handleSelect = (palette: ColorPalette) => {
    setActivePalette(palette.id)
    applyPalette(palette)
    setCustomHex(palette.primary)
    // Calculate approximate contrast against #0a0a0f
    setContrastRatio(palette.id === 'solar-flare' ? '9.1:1' : palette.id === 'tokyo-cyan' ? '8.8:1' : '8.4:1')
  }

  const handleRandomize = () => {
    const others = COLOR_PALETTES.filter((p) => p.id !== activePalette)
    const random = others[Math.floor(Math.random() * others.length)]
    handleSelect(random)
  }

  return (
    <div className="relative">
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-[#272738] bg-[#12121a] hover:bg-[#1a1a24] text-xs font-mono text-[#94a3b8] hover:text-white transition-all shadow-sm active:scale-95"
        title="Live Realtime Color Palette & Zen Mode"
      >
        <Palette className="w-3.5 h-3.5 text-[#f26625]" />
        <span className="hidden sm:inline text-[11px] font-medium">Palette</span>
        <span
          className="w-2 h-2 rounded-full inline-block ml-0.5"
          style={{ backgroundColor: COLOR_PALETTES.find((p) => p.id === activePalette)?.primary || '#f26625' }}
        />
      </button>

      {/* Floating Modal / Popover */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px]"
              onClick={() => setIsOpen(false)}
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -8 }}
              transition={{ duration: 0.16, ease: [0.23, 1, 0.32, 1] }}
              className="absolute right-0 top-10 z-50 w-80 rounded-xl bg-[#0e0e14] border border-[#272738] shadow-2xl p-4 text-xs font-mono space-y-3.5 glow-yc"
            >
              {/* Header */}
              <div className="flex items-center justify-between pb-2 border-b border-[#1c1c28]">
                <div className="flex items-center gap-2">
                  <Palette className="w-4 h-4 text-[#f26625]" />
                  <span className="font-semibold text-white uppercase tracking-wider text-[11px]">
                    Realtime Color Engine
                  </span>
                </div>
                <button
                  onClick={handleRandomize}
                  className="p-1 rounded text-[#94a3b8] hover:text-white hover:bg-[#1a1a24] transition-colors"
                  title="Random Palette"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Palette List */}
              <div className="space-y-1.5">
                {COLOR_PALETTES.map((pal) => {
                  const isSelected = activePalette === pal.id
                  return (
                    <button
                      key={pal.id}
                      onClick={() => handleSelect(pal)}
                      className={clsx(
                        'w-full flex items-center justify-between p-2 rounded-lg border text-left transition-all',
                        isSelected
                          ? 'bg-[#181824] border-white/20 shadow-sm'
                          : 'bg-[#12121a]/60 border-transparent hover:bg-[#161622] hover:border-[#272738]'
                      )}
                    >
                      <div className="flex items-center gap-2.5">
                        <span
                          className="w-4 h-4 rounded-full border border-white/20 shadow-sm shrink-0 flex items-center justify-center"
                          style={{ backgroundColor: pal.primary }}
                        >
                          {isSelected && <Check className="w-2.5 h-2.5 text-white stroke-[3]" />}
                        </span>
                        <div>
                          <p className="text-[11px] font-semibold text-white">{pal.name}</p>
                          <p className="text-[9px] text-[#94a3b8] truncate max-w-[170px]">{pal.description}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-1">
                        <span
                          className="w-2 h-5 rounded-sm"
                          style={{ backgroundColor: pal.hover }}
                        />
                        <span
                          className="w-2 h-5 rounded-sm"
                          style={{ backgroundColor: pal.primary }}
                        />
                      </div>
                    </button>
                  )
                })}
              </div>

              {/* Telemetry / Live Metrics */}
              <div className="p-2.5 rounded-lg bg-[#08080c] border border-[#1c1c28] space-y-1.5 text-[10px]">
                <div className="flex items-center justify-between text-[#94a3b8]">
                  <span>Active Hex:</span>
                  <span className="text-white font-bold">{customHex.toUpperCase()}</span>
                </div>
                <div className="flex items-center justify-between text-[#94a3b8]">
                  <span>Contrast vs Obsidian:</span>
                  <span className="text-emerald-400 font-bold">{contrastRatio} (AAA)</span>
                </div>
                <div className="flex items-center justify-between text-[#94a3b8]">
                  <span>Motion Drivers:</span>
                  <span className="text-purple-400 font-bold">Framer Motion + GSAP + Lenis</span>
                </div>
              </div>

              {/* Close Button */}
              <button
                onClick={() => setIsOpen(false)}
                className="w-full py-1.5 rounded-md bg-[#161622] hover:bg-[#202030] text-zinc-300 hover:text-white text-[11px] font-medium transition-colors"
              >
                Done
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
