"use client"

import { useReducedMotion } from "framer-motion"

export type MascotSize = "large" | "medium"

const SIZES: Record<MascotSize, { width: number; height: number }> = {
  large: { width: 280, height: 280 },
  medium: { width: 160, height: 160 },
}

const ALT =
  "Raso, the RasoSynthTune assistant, a glossy white robot with a dark face screen, sparkling eyes, an open smile, and a glowing orange core, waving hello"

// Standalone white robot artwork (user choice, 2026-10-29). This is ONE flat
// image, so its hand cannot move independently: the waving pose is baked into
// the artwork itself. Whole-image motion only: the wrapper bobs, the image
// sways gently and its glow pulses. Keyframes live in frontend/app/globals.css.
// With reduced motion, no animation classes are applied and the mascot is static.
export function Mascot({ size = "large", className }: { size?: MascotSize; className?: string }) {
  const reduceMotion = useReducedMotion()
  const dims = SIZES[size]
  const a = (cls: string) => (reduceMotion ? "" : cls)
  const outer = className ? className + " " + a("mascot-float") : a("mascot-float")
  return (
    <div
      className={outer}
      style={{ width: dims.width, height: dims.height }}
      role="img"
      aria-label={ALT}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/mascot-standalone.webp"
        alt={ALT}
        width={dims.width}
        height={dims.height}
        className={a("mascot-sway-img") + " " + a("mascot-glow")}
        style={{ width: dims.width, height: dims.height, objectFit: "contain" }}
      />
    </div>
  )
}
