"use client"

import { useReducedMotion } from "framer-motion"

export type MascotSize = "large" | "medium"

const SIZES: Record<MascotSize, { width: number; height: number }> = {
  large: { width: 280, height: 280 },
  medium: { width: 160, height: 160 },
}

const ALT =
  "Raso, the RasoSynthTune assistant, a glossy white robot with a dark face screen, big sparkling eyes, an open smile, and a glowing orange core, waving hello"

// Standalone white robot as a transparent-background cut of the ACTUAL raster
// artwork (background removed to alpha, no black box). The layered SVG
// recreation was abandoned after the user sighted an inverted/broken look
// (black body, stick arms) in a preview: what ships now is unmistakably the
// real robot — white glossy body, dark face screen only, proper waving arm
// and hands, orange core, orange-tipped antenna.
// Honest motion limit: this is ONE flat cutout image, so its hand cannot move
// independently — the waving pose is baked into the artwork itself.
// Whole-image motion only: wrapper bob, gentle sway, soft glow pulse, all
// looping. With reduced motion, no animation classes are applied and the
// mascot is static. Keyframes live in frontend/app/globals.css.
export function Mascot({ size = "large", className }: { size?: MascotSize; className?: string }) {
  const reduceMotion = useReducedMotion()
  const dims = SIZES[size]
  const a = (cls: string) => (reduceMotion ? "" : cls)
  const outer = className ? className + " " + a("mascot-bob") : a("mascot-bob")
  return (
    <div
      className={outer}
      style={{ width: dims.width, height: dims.height, background: "transparent" }}
      role="img"
      aria-label={ALT}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/mascot-standalone-cutout.webp"
        alt={ALT}
        width={dims.width}
        height={dims.height}
        className={a("mascot-sway-img") + " " + a("mascot-glow")}
        style={{ width: dims.width, height: dims.height, objectFit: "contain", background: "transparent" }}
      />
    </div>
  )
}
