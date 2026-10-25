'use client'

import React, { createContext, useContext, useRef, useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import gsap from 'gsap'
import {
  Sparkles,
  Maximize2,
  Minimize2,
  Activity,
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

  const [telemetry, setTelemetry] = useState({
    fps: 60,
    latency: '14ms',
    merkleSync: '100% Sealed',
    nodesOnline: '8 / 8 Active',
  })

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

        {/* Aperture Telemetry Bar */}
        <div className="relative z-10 flex items-center justify-between px-5 py-3 border-b border-[#1c1c28]/60 backdrop-blur-sm text-[10px] font-mono text-[#64748b]">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1 text-emerald-400 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              SYNTH_KERNEL_ONLINE
            </span>
            <span className="hidden sm:inline text-[#334155]">/</span>
            <span className="hidden sm:inline text-slate-400">{telemetry.nodesOnline}</span>
            <span className="hidden sm:inline text-[#334155]">/</span>
            <span className="hidden sm:inline text-purple-300">DBOM: {telemetry.merkleSync}</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={toggleZenMode}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[10px] font-mono font-medium transition-all ${
                isZenMode
                  ? 'bg-[#f26625] text-white shadow-sm'
                  : 'bg-[#12121a] hover:bg-[#1c1c28] text-zinc-300 hover:text-white border border-[#272738]'
              }`}
              title="Toggle Zen Density ('Looks empty, not actually empty')"
            >
              {isZenMode ? (
                <>
                  <Minimize2 className="w-3 h-3 text-white" />
                  <span>Lab View</span>
                </>
              ) : (
                <>
                  <Maximize2 className="w-3 h-3 text-[#f26625]" />
                  <span>Zen Spatial</span>
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
              <span className="text-[10px] text-zinc-400">Press Lab View to expand controls</span>
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

        {/* Bottom Subtle Telemetry Status Dock */}
        <motion.div
          initial={{ opacity: 0.7 }}
          whileHover={{ opacity: 1 }}
          className="relative z-10 px-5 py-2.5 border-t border-[#1c1c28]/60 bg-[#0a0a10]/80 backdrop-blur-md flex flex-wrap items-center justify-between text-[10px] font-mono text-[#64748b] gap-2"
        >
          <div className="flex items-center gap-4">
            <span className="text-zinc-500 flex items-center gap-1">
              <Activity className="w-3 h-3 text-[#f26625]" />
              Latency: <strong className="text-white font-normal">{telemetry.latency}</strong>
            </span>
            <span className="hidden md:inline text-zinc-500">
              Motion Engine: <strong className="text-white font-normal">Framer Motion + GSAP + Lenis</strong>
            </span>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-[9px] text-zinc-500 uppercase tracking-widest">
              State: <span className="text-zinc-300 font-bold">{isZenMode ? 'Zen Spatial Void' : activeMode}</span>
            </span>
          </div>
        </motion.div>
      </motion.div>
    </ZenSpatialContext.Provider>
  )
}
