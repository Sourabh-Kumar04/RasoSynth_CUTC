'use client'

import React, { createContext, useContext, useRef, useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import gsap from 'gsap'
import {
  Sparkles,
  Maximize2,
  Minimize2,
  Layers,
  Compass,
} from 'lucide-react'
import { playClickSound } from '@/lib/audio/sound-effects'

interface ZenContextType {
  isZenMode: boolean
  toggleZenMode: () => void
}

const ZenSpatialContext = createContext<ZenContextType>({
  isZenMode: false,
  toggleZenMode: () => {},
})

export function useZenSpatial() {
  return useContext(ZenSpatialContext)
}

export function ZenSpatialCanvas({
  children,
  activeMode = 'Zen Kinetic Spatial',
  isZenMode: controlledZenMode,
  onZenModeChange,
}: {
  children?: React.ReactNode
  activeMode?: string
  isZenMode?: boolean
  onZenModeChange?: (zen: boolean) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const auraRef = useRef<HTMLDivElement>(null)
  const [internalZenMode, setInternalZenMode] = useState(false)
  
  const isZenMode = controlledZenMode !== undefined ? controlledZenMode : internalZenMode

  // GSAP 60fps Smooth Pointer Aura Tracking
  useEffect(() => {
    if (!containerRef.current || !auraRef.current) return

    const container = containerRef.current
    const aura = auraRef.current

    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top

      gsap.to(aura, {
        x: x - 150,
        y: y - 150,
        duration: 0.65,
        ease: 'power3.out',
      })
    }

    container.addEventListener('mousemove', handleMouseMove)
    return () => container.removeEventListener('mousemove', handleMouseMove)
  }, [])

  const toggleZenMode = () => {
    playClickSound()
    if (onZenModeChange) {
      onZenModeChange(!isZenMode)
    } else {
      setInternalZenMode((prev) => !prev)
    }
  }

  return (
    <ZenSpatialContext.Provider value={{ isZenMode, toggleZenMode }}>
      <motion.div
        ref={containerRef}
        layout
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        className={`relative w-full rounded-2xl border transition-all duration-500 shadow-2xl overflow-hidden ${
          isZenMode
            ? 'border-[#f26625]/40 bg-[#07070b] py-2'
            : 'border-[#272738]/60 bg-[#08080c]'
        }`}
      >
        {/* GSAP Radial Glow Aura */}
        <div
          ref={auraRef}
          className="pointer-events-none absolute -top-0 -left-0 w-[350px] h-[350px] rounded-full bg-[radial-gradient(circle,rgba(242,102,37,0.12)_0%,transparent_70%)] blur-2xl"
        />

        {/* Subtle Micro-Grid Backdrop */}
        <div className="absolute inset-0 bg-dot-grid opacity-25 pointer-events-none" />

        {/* Aperture Controls Bar */}
        <div className="relative z-10 flex items-center justify-end px-5 py-2.5 border-b border-[#1c1c28]/60 backdrop-blur-sm text-xs font-mono text-[#64748b]">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={toggleZenMode}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-medium transition-all ${
                isZenMode
                  ? 'bg-[#f26625] text-white shadow-sm'
                  : 'bg-[#12121a] hover:bg-[#1c1c28] text-zinc-300 hover:text-white border border-[#272738]'
              }`}
              title="Toggle between Full Studio Controls and Focused Minimal Canvas"
            >
              {isZenMode ? (
                <>
                  <Minimize2 className="w-3 h-3 text-white" />
                  <span>Exit Focus Mode</span>
                </>
              ) : (
                <>
                  <Maximize2 className="w-3 h-3 text-[#f26625]" />
                  <span>Focus Mode (Simplified)</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Zen Mode Ambient Notification Banner */}
        <AnimatePresence>
          {isZenMode && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="relative z-10 px-6 py-2.5 bg-[#f26625]/10 border-b border-[#f26625]/20 flex items-center justify-between text-xs font-mono text-[#f26625]"
            >
              <span className="flex items-center gap-2">
                <Compass className="w-3.5 h-3.5 animate-spin" style={{ animationDuration: '8s' }} />
                <span>Zen Spatial Density Active: Secondary chrome suppressed · Deep negative space</span>
              </span>
              <span className="text-xs text-zinc-400">Press Lab View to expand controls</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Main Content Space */}
        <motion.div
          layout
          className={`relative z-10 transition-all duration-300 ${
            isZenMode ? 'p-6 sm:p-10 lg:p-14 max-w-4xl mx-auto' : 'p-4 sm:p-6 lg:p-8'
          }`}
        >
          {children}
        </motion.div>
      </motion.div>
    </ZenSpatialContext.Provider>
  )
}
