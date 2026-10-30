"use client"

import React, { useState, useEffect, useMemo, useCallback, useRef } from "react"
import { useReducedMotion } from "framer-motion"

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

// Animation cycles built from the 12 extracted pose frames
const ANIMATION_CYCLES: Record<MascotState, { frames: string[]; intervalMs: number }> = {
  wave: {
    frames: ["wave-1", "wave-2", "wave-3", "wave-4", "wave-3", "wave-2"],
    intervalMs: 250,
  },
  thinking: {
    frames: ["thinking", "thinking", "alert", "working", "working", "alert"],
    intervalMs: 480,
  },
  idle: {
    frames: ["idle", "idle", "idle", "alert"],
    intervalMs: 900,
  },
  alert: {
    frames: ["alert", "idle"],
    intervalMs: 700,
  },
  working: {
    frames: ["working", "alert", "working", "thinking"],
    intervalMs: 380,
  },
  pointing: {
    frames: ["pointing", "pointing", "alert", "idle"],
    intervalMs: 500,
  },
  cheering: {
    frames: ["cheering", "wave-2", "cheering", "celebrate"],
    intervalMs: 260,
  },
  confused: {
    frames: ["confused", "confused", "alert", "confused"],
    intervalMs: 650,
  },
  celebrate: {
    frames: ["celebrate", "cheering", "wave-2", "celebrate"],
    intervalMs: 220,
  },
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
  const reduceMotion = useReducedMotion()
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
  const [frameIndex, setFrameIndex] = useState(0)

  // Keep activeState in sync when prop changes unless a reaction is playing
  useEffect(() => {
    setActiveState(state)
    setFrameIndex(0)
  }, [state])

  const cycle = useMemo(() => ANIMATION_CYCLES[activeState], [activeState])

  // Pose frame animation loop
  useEffect(() => {
    if (reduceMotion) {
      setFrameIndex(0)
      return
    }

    const timer = setInterval(() => {
      setFrameIndex((prev) => (prev + 1) % cycle.frames.length)
    }, cycle.intervalMs)

    return () => clearInterval(timer)
  }, [cycle, reduceMotion])

  // Interactive reaction: click triggers a celebration or cheer burst, then reverts
  const handleClick = useCallback(() => {
    if (onClick) {
      onClick()
    }
    if (!interactive) return

    if (revertTimerRef.current) {
      clearTimeout(revertTimerRef.current)
    }

    // Trigger celebration reaction
    const reactionState: MascotState = activeState === "confused" ? "alert" : "celebrate"
    setActiveState(reactionState)
    setFrameIndex(0)

    revertTimerRef.current = setTimeout(() => {
      setActiveState(state)
      setFrameIndex(0)
    }, 1800)
  }, [onClick, interactive, activeState, state])

  // Frame to render
  const currentFrame = reduceMotion ? cycle.frames[0] : cycle.frames[frameIndex] || cycle.frames[0]
  const imageSrc = `/mascot/${currentFrame}.webp`
  const altText = ALT_DESCRIPTIONS[activeState]

  const outerClass = [
    className,
    reduceMotion ? "" : "mascot-bob",
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
      title={interactive ? "Click me!" : undefined}
    >
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
          filter: "drop-shadow(0 8px 24px rgba(242, 102, 37, 0.18))",
        }}
      />
    </div>
  )
}
