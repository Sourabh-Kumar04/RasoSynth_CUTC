"use client"

import React from "react"

export interface BrandLogoProps {
  className?: string
  size?: number
  showWordmark?: boolean
  wordmarkClassName?: string
  showBadge?: boolean
  variant?: "dark" | "light"
}

export function BrandLogo({
  className = "",
  size = 32,
  showWordmark = false,
  wordmarkClassName = "",
  showBadge = false,
}: BrandLogoProps) {
  const uid = React.useId().replace(/:/g, "")
  const gradId = `raso-grad-${uid}`
  const glowId = `raso-glow-${uid}`

  return (
    <div className={"inline-flex items-center gap-2.5 " + className}>
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
          <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FF7A1A" />
            <stop offset="48%" stopColor="#FF385C" />
            <stop offset="100%" stopColor="#8A3FFC" />
          </linearGradient>
          <radialGradient id={glowId} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#FF385C" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#FF7A1A" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Ambient subtle backplate */}
        <rect
          x="2"
          y="2"
          width="36"
          height="36"
          rx="10"
          fill="#0c0b12"
          stroke="rgba(255, 255, 255, 0.1)"
          strokeWidth="1"
        />
        <circle cx="20" cy="20" r="13" fill={`url(#${glowId})`} />

        {/* Convergent synthesis glyph */}
        <path
          d="M13 11C13 10.45 13.45 10 14 10H22C26.14 10 29.5 13.36 29.5 17.5C29.5 21.05 27.04 24.03 23.7 24.81L29.4 30.08C29.98 30.62 29.6 31.6 28.82 31.6H26.15C25.7 31.6 25.26 31.4 24.95 31.05L19.45 24.8H16.2V30.6C16.2 31.15 15.75 31.6 15.2 31.6H14C13.45 31.6 13 31.15 13 30.6V11ZM16.2 20.8H21.8C23.62 20.8 25.1 19.32 25.1 17.5C25.1 15.68 23.62 14.2 21.8 14.2H16.2V20.8Z"
          fill={`url(#${gradId})`}
        />
        {/* Luminous beacon */}
        <circle cx="29" cy="17.5" r="2.2" fill="#FFB020" />
      </svg>

      {showWordmark && (
        <div className="flex items-center gap-2">
          <span className={"font-sans tracking-tight font-bold text-white text-[15px] leading-none " + wordmarkClassName}>
            Raso<span className="bg-gradient-to-r from-[#FF7A1A] via-[#FF385C] to-[#A855F7] bg-clip-text text-transparent font-extrabold">Synth</span><span className="text-zinc-300 font-medium">Tune</span>
          </span>
          {showBadge && (
            <span className="px-1.5 py-0.5 text-[10px] font-mono font-bold tracking-wider text-[#FF7A1A] bg-[#FF7A1A]/10 border border-[#FF7A1A]/20 rounded-full">
              Enterprise
            </span>
          )}
        </div>
      )}
    </div>
  )
}

export default BrandLogo
