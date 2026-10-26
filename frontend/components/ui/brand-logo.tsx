'use client'

import React, { useId } from 'react'

export interface BrandLogoProps {
  className?: string
  size?: number
  showWordmark?: boolean
  wordmarkClassName?: string
}

export function BrandLogo({
  className = '',
  size = 32,
  showWordmark = false,
  wordmarkClassName = '',
}: BrandLogoProps) {
  // SVG ids are document-global. A component-local prefix prevents one logo
  // instance from accidentally borrowing another instance's gradients.
  const idPrefix = useId().replace(/:/g, '')
  const primaryGradient = `${idPrefix}-primary`
  const sparkGradient = `${idPrefix}-spark`
  const containerGradient = `${idPrefix}-container`
  const glowFilter = `${idPrefix}-glow`

  return (
    <div className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0 transition-transform duration-200 group-hover:scale-105"
        role="img"
        aria-label="RasoSynthTune"
      >
        <defs>
          <linearGradient id={primaryGradient} x1="4" y1="4" x2="36" y2="36" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#f26625" />
            <stop offset="50%" stopColor="#ff8533" />
            <stop offset="100%" stopColor="#ea580c" />
          </linearGradient>

          <linearGradient id={sparkGradient} x1="14" y1="10" x2="28" y2="28" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="40%" stopColor="#ffedd5" />
            <stop offset="100%" stopColor="#f26625" />
          </linearGradient>

          <linearGradient id={containerGradient} x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#1a120e" />
            <stop offset="100%" stopColor="#0a0a0f" />
          </linearGradient>

          <filter id={glowFilter} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        <rect
          x="1"
          y="1"
          width="38"
          height="38"
          rx="10"
          fill={`url(#${containerGradient})`}
          stroke="#f26625"
          strokeOpacity="0.4"
          strokeWidth="1.5"
        />

        <circle cx="20" cy="20" r="12" fill="#f26625" fillOpacity="0.12" />

        <path
          d="M20 5.5L32.5 12.8V27.2L20 34.5L7.5 27.2V12.8L20 5.5Z"
          stroke={`url(#${primaryGradient})`}
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeOpacity="0.8"
        />

        <circle cx="20" cy="5.5" r="1.5" fill="#f26625" />
        <circle cx="32.5" cy="12.8" r="1.5" fill="#ff8533" />
        <circle cx="32.5" cy="27.2" r="1.5" fill="#ea580c" />
        <circle cx="20" cy="34.5" r="1.5" fill="#f26625" />
        <circle cx="7.5" cy="27.2" r="1.5" fill="#ea580c" />
        <circle cx="7.5" cy="12.8" r="1.5" fill="#ff8533" />

        <path
          d="M14.5 28V12H21.5C24.5 12 26.5 14 26.5 16.8C26.5 19.6 24.5 21.6 21.5 21.6H14.5M20 21.6L26.5 28"
          stroke={`url(#${sparkGradient})`}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter={`url(#${glowFilter})`}
        />

        <path
          d="M20.5 16.8L21.7 14.8L22.9 16.8L25 17.5L22.9 18.2L21.7 20.2L20.5 18.2L18.4 17.5L20.5 16.8Z"
          fill="#ffffff"
          opacity="0.95"
        />
      </svg>

      {showWordmark && (
        <span className={`font-display font-bold tracking-[-0.045em] text-white leading-none ${wordmarkClassName}`}>
          Raso<span className="text-[#f26625]">Synth</span><span className="text-zinc-400">Tune</span>
        </span>
      )}
    </div>
  )
}
export default BrandLogo
