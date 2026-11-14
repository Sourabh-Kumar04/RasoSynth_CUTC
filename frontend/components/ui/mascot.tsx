"use client"

import React, { useState, useEffect, useCallback, useRef } from "react"

export type MascotSize = "large" | "medium" | "small"

export type MascotState =
  | "wave"
  | "thinking"
  | "idle"
  | "alert"
  | "working"
  | "pointing"
  | "cheering"
  | "confused"
  | "celebrate"

const ALL_POSES = [
  "alert",
  "celebrate",
  "cheering",
  "confused",
  "idle",
  "pointing",
  "thinking",
  "wave-1",
  "wave-2",
  "wave-3",
  "wave-4",
  "working",
] as const

const SIZES: Record<MascotSize, { width: number; height: number }> = {
  large: { width: 280, height: 280 },
  medium: { width: 160, height: 160 },
  small: { width: 96, height: 96 },
}

const ALT_DESCRIPTIONS: Record<MascotState, string> = {
  wave: "Raso, the RasoSynthTune mascot, waving hello with a friendly digital smile",
  thinking: "Raso, the RasoSynthTune mascot, in deep contemplative thought analyzing datasets",
  idle: "Raso, the RasoSynthTune mascot, resting in idle standby mode",
  alert: "Raso, the RasoSynthTune mascot, attentively listening and ready to assist",
  working: "Raso, the RasoSynthTune mascot, actively synthesizing and verifying datasets",
  pointing: "Raso, the RasoSynthTune mascot, gesturing towards actions and workflow options",
  cheering: "Raso, the RasoSynthTune mascot, cheering enthusiastically",
  confused: "Raso, the RasoSynthTune mascot, looking puzzled and searching for the missing resource",
  celebrate: "Raso, the RasoSynthTune mascot, celebrating dataset completion with joyful dancing",
}

// Canonical single-pose mapping for each state (clean, stable, no frantic flipbook cycling)
const STATE_FRAMES: Record<MascotState, string> = {
  wave: "wave-1",
  thinking: "thinking",
  idle: "idle",
  alert: "alert",
  working: "working",
  pointing: "pointing",
  cheering: "cheering",
  confused: "confused",
  celebrate: "celebrate",
}

export interface MascotProps {
  size?: MascotSize
  state?: MascotState
  className?: string
  interactive?: boolean
  onClick?: () => void
}

export function Mascot({
  size = "large",
  state = "wave",
  className,
  interactive = true,
  onClick,
}: MascotProps) {
  const dims = SIZES[size]
  const revertTimerRef = useRef<NodeJS.Timeout | null>(null)

  // Preload all 12 pose frames on client mount to eliminate frame swap flicker
  useEffect(() => {
    if (typeof window !== "undefined") {
      ALL_POSES.forEach((pose) => {
        const img = new Image()
        img.src = `/mascot/${pose}.webp`
      })
    }
  }, [])

  // Cleanup pending reaction timers on unmount
  useEffect(() => {
    return () => {
      if (revertTimerRef.current) {
        clearTimeout(revertTimerRef.current)
      }
    }
  }, [])

  // Active state can temporarily switch on interactive triggers (click/reaction)
  const [activeState, setActiveState] = useState<MascotState>(state)

  // Keep activeState in sync when prop changes
  useEffect(() => {
    setActiveState(state)
  }, [state])

  // Interactive reaction: click triggers a celebration or cheer burst, then reverts
  const handleClick = useCallback(() => {
    if (onClick) {
      onClick()
    }
    if (!interactive) return

    if (revertTimerRef.current) {
      clearTimeout(revertTimerRef.current)
    }

    // Trigger subtle reaction
    const reactionState: MascotState = activeState === "confused" ? "alert" : "celebrate"
    setActiveState(reactionState)

    revertTimerRef.current = setTimeout(() => {
      setActiveState(state)
    }, 1200)
  }, [onClick, interactive, activeState, state])

  // Frame to render (stable, high-fidelity canonical pose)
  const currentFrame = STATE_FRAMES[activeState] || "idle"
  const imageSrc = `/mascot/${currentFrame}.webp`
  const altText = ALT_DESCRIPTIONS[activeState]

  const outerClass = [
    className,
    interactive ? "cursor-pointer select-none transition-transform duration-200 hover:scale-105 active:scale-95" : "",
  ]
    .filter(Boolean)
    .join(" ")

  return (
    <div
      className={outerClass}
      style={{
        position: "relative",
        width: dims.width,
        height: dims.height,
        background: "transparent",
      }}
      role="img"
      aria-label={altText}
      onClick={interactive ? handleClick : undefined}
    >
      {/* Contrast guardian halo: ensures white robot body and helmet stand out cleanly on any light or dark background */}
      <div
        className="absolute inset-1 -z-10 rounded-full pointer-events-none"
        style={{
          background:
            "radial-gradient(circle at 50% 52%, rgba(14, 13, 22, 0.72) 0%, rgba(10, 10, 16, 0.45) 55%, transparent 75%)",
          filter: "blur(10px)",
        }}
      />

      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={imageSrc}
        alt=""
        width={dims.width}
        height={dims.height}
        style={{
          width: dims.width,
          height: dims.height,
          objectFit: "contain",
          background: "transparent",
          display: "block",
          filter:
            "drop-shadow(0 4px 14px rgba(0, 0, 0, 0.55)) drop-shadow(0 1px 3px rgba(0, 0, 0, 0.45)) drop-shadow(0 10px 28px rgba(242, 102, 37, 0.26))",
        }}
      />
    </div>
  )
}
