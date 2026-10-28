'use client'

import React, { useId } from 'react'

export interface BrandLogoProps {
  className?: string
  size?: number
  showWordmark?: boolean
  wordmarkClassName?: string
  showBadge?: boolean
}

export function BrandLogo({
  className = '',
  size = 34,
  showWordmark = false,
  wordmarkClassName = '',
  showBadge = false,
}: BrandLogoProps) {
  // SVG ids are document-global. A component-local prefix prevents one logo
  // instance from accidentally borrowing another instance's gradients/filters.
  const idPrefix = useId().replace(/:/g, '')
  const gradientPrimary = `${idPrefix}-p`
  const gradientAccent = `${idPrefix}-acc`
  const gradientRim = `${idPrefix}-rim`
  const gradientBg = `${idPrefix}-bg`
  const gradientGlow = `${idPrefix}-glow`
  const glowFilter = `${idPrefix}-filter-glow`

  return (
    <div className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0 transition-all duration-300 group-hover:scale-105 group-hover:drop-shadow-[0_0_12px_rgba(242,102,37,0.35)]"
        role="img"
        aria-label="RasoSynthTune"
      >
        <defs>
          {/* Obsidian Tile Background */}
          <linearGradient id={gradientBg} x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#181824" />
            <stop offset="50%" stopColor="#0f0f17" />
            <stop offset="100%" stopColor="#07070a" />
          </linearGradient>

          {/* Premium Metallic & Signal-Orange Rim */}
          <linearGradient id={gradientRim} x1="2" y1="2" x2="38" y2="38" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.32" />
            <stop offset="25%" stopColor="#f26625" stopOpacity="0.8" />
            <stop offset="70%" stopColor="#ea580c" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#7c3aed" stopOpacity="0.15" />
          </linearGradient>

          {/* Ambient Core Glow */}
          <radialGradient id={gradientGlow} cx="50%" cy="45%" r="55%">
            <stop offset="0%" stopColor="#f26625" stopOpacity="0.35" />
            <stop offset="50%" stopColor="#ea580c" stopOpacity="0.12" />
            <stop offset="100%" stopColor="#f26625" stopOpacity="0" />
          </radialGradient>

          {/* Primary Synthesis Flame Ribbon */}
          <linearGradient id={gradientPrimary} x1="10" y1="8" x2="30" y2="32" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="15%" stopColor="#fed7aa" />
            <stop offset="45%" stopColor="#f26625" />
            <stop offset="85%" stopColor="#ea580c" />
            <stop offset="100%" stopColor="#c2410c" />
          </linearGradient>

          {/* Harmonic Convergence Wave (Gold / Amber Accent) */}
          <linearGradient id={gradientAccent} x1="28" y1="12" x2="14" y2="28" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#fef08a" />
            <stop offset="40%" stopColor="#f59e0b" />
            <stop offset="100%" stopColor="#f26625" />
          </linearGradient>

          {/* Micro Specular Soft Glow Filter */}
          <filter id={glowFilter} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Outer Squircle Container */}
        <rect
          x="1.5"
          y="1.5"
          width="37"
          height="37"
          rx="10"
          fill={`url(#${gradientBg})`}
          stroke={`url(#${gradientRim})`}
          strokeWidth="1.2"
        />

        {/* Ambient Warm Neural Core */}
        <circle cx="20" cy="19" r="14" fill={`url(#${gradientGlow})`} />

        {/* Geometric Hexagonal Calibration Guide (Micro-Subtle) */}
        <path
          d="M20 7.5L30.5 13.5V25.5L20 31.5L9.5 25.5V13.5L20 7.5Z"
          stroke="#ffffff"
          strokeWidth="0.8"
          strokeOpacity="0.08"
          strokeDasharray="2 2"
        />

        {/* Harmonic Counter-Wave (Creates dimensional 'S' confluence) */}
        <path
          d="M26.5 12C28.5 15 28 19 24.5 21C21 23 18.5 24.5 15.5 28"
          stroke={`url(#${gradientAccent})`}
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeOpacity="0.85"
        />

        {/* Signature Monogram: The Quantum Synthesis 'R' */}
        {/* Continuous sculpted ribbon: vertical pillar -> circular head loop -> forward dynamic vector */}
        <path
          d="M13.5 28.5V12C13.5 11.17 14.17 10.5 15 10.5H21C24.866 10.5 27.5 12.8 27.5 16C27.5 19.1 25 21.2 21.2 21.2H14M19.8 21.2L27 28.5"
          stroke={`url(#${gradientPrimary})`}
          strokeWidth="2.75"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter={`url(#${glowFilter})`}
        />

        {/* Specular Apex Highlight Flare */}
        <path
          d="M21 13.5L21.7 15.2L23.4 16L21.7 16.8L21 18.5L20.3 16.8L18.6 16L20.3 15.2L21 13.5Z"
          fill="#ffffff"
          opacity="0.95"
        />

        {/* Micro Calibration Vertex Nodes */}
        <circle cx="13.5" cy="11.5" r="1" fill="#ffffff" opacity="0.9" />
        <circle cx="27" cy="28.5" r="1.2" fill="#f26625" />
      </svg>

      {showWordmark && (
        <div className="flex items-center gap-1.5">
          <span className={`font-display font-bold tracking-[-0.04em] text-white leading-none ${wordmarkClassName}`}>
            Raso<span className="bg-gradient-to-r from-[#f26625] via-[#ff8238] to-[#f59e0b] bg-clip-text text-transparent">Synth</span><span className="text-[#94a3b8] font-semibold">Tune</span>
          </span>
          {showBadge && (
            <span className="px-1.5 py-0.5 text-xs font-mono font-bold tracking-wider text-[#f26625] bg-[#f26625]/10 border border-[#f26625]/25 rounded">
              2.0
            </span>
          )}
        </div>
      )}
    </div>
  )
}

export default BrandLogo
