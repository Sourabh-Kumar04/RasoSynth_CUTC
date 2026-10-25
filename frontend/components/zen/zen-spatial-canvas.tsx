'use client'

import { useRef, useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import gsap from 'gsap'
import {
  Sparkles,
  Command,
  Database,
  ShieldCheck,
  Activity,
  Layers,
  ArrowRight,
  Maximize2,
  Minimize2,
  Zap,
} from 'lucide-react'
import Link from 'next/link'

export function ZenSpatialCanvas({
  children,
  activeMode = 'Zen Minimalist',
}: {
  children?: React.ReactNode
  activeMode?: string
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const auraRef = useRef<HTMLDivElement>(null)
  const [isHovered, setIsHovered] = useState(false)
  const [zenExpanded, setZenExpanded] = useState(false)
  const [telemetry, setTelemetry] = useState({
    fps: 60,
    latency: '14ms',
    merkleSync: '100% Sealed',
    nodesOnline: '8 / 8 Active',
  })

  // GSAP Mouse Aura Tracking
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
        duration: 0.7,
        ease: 'power3.out',
      })
    }

    container.addEventListener('mousemove', handleMouseMove)
    return () => container.removeEventListener('mousemove', handleMouseMove)
  }, [])

  return (
    <div
      ref={containerRef}
      className="relative w-full rounded-2xl border border-[#272738]/60 bg-[#08080c] overflow-hidden transition-all duration-500 shadow-2xl"
    >
      {/* GSAP Reactive Radial Glow Aura */}
      <div
        ref={auraRef}
        className="pointer-events-none absolute -top-0 -left-0 w-[300px] h-[300px] rounded-full bg-[radial-gradient(circle,rgba(242,102,37,0.12)_0%,transparent_70%)] blur-2xl"
      />

      {/* Subtle Micro-Grid Backdrop ("Looks empty, but structured") */}
      <div className="absolute inset-0 bg-dot-grid opacity-30 pointer-events-none" />

      {/* Top Telemetry Aperture Bar */}
      <div className="relative z-10 flex items-center justify-between px-5 py-3 border-b border-[#1c1c28]/60 backdrop-blur-sm text-[10px] font-mono text-[#64748b]">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1 text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            SYNTH_KERNEL_ONLINE
          </span>
          <span className="hidden sm:inline text-[#334155]">/</span>
          <span className="hidden sm:inline text-slate-400 font-semibold">{telemetry.nodesOnline}</span>
          <span className="hidden sm:inline text-[#334155]">/</span>
          <span className="hidden sm:inline text-purple-300">DBOM: {telemetry.merkleSync}</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setZenExpanded(!zenExpanded)}
            className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#12121a] hover:bg-[#1c1c28] text-zinc-400 hover:text-white transition-colors"
            title="Toggle Zen Density"
          >
            {zenExpanded ? <Minimize2 className="w-3 h-3 text-[#f26625]" /> : <Maximize2 className="w-3 h-3 text-[#f26625]" />}
            <span className="text-[9px] uppercase">{zenExpanded ? 'Compact' : 'Zen View'}</span>
          </button>
        </div>
      </div>

      {/* Main Content Space */}
      <div className="relative z-10 p-4 sm:p-6 lg:p-8">
        {children}
      </div>

      {/* Bottom Subtle Telemetry Status Dock (Subtle density revealed on hover) */}
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
            Physics: <strong className="text-white font-normal">Framer Motion + GSAP + Lenis</strong>
          </span>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-[9px] text-zinc-500 uppercase tracking-widest">
            Aesthetic: <span className="text-zinc-300 font-bold">{activeMode}</span>
          </span>
        </div>
      </motion.div>
    </div>
  )
}
