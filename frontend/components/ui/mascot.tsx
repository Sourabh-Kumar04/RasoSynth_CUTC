"use client"

import { useReducedMotion } from "framer-motion"

export type MascotSize = "large" | "medium"

const SIZES: Record<MascotSize, { width: number; height: number }> = {
  large: { width: 280, height: 280 },
  medium: { width: 160, height: 160 },
}

const ALT =
  "Raso, the RasoSynthTune assistant, a glossy white robot with a dark face screen, big sparkling eyes, an open smile, and a glowing orange core, waving hello"

// Layered RASTER mascot: the SAME standalone white robot cutout, segmented
// into its own pixels (see make_layers.py) so each part genuinely moves:
// body (static base), sway arm, waving arm, head (tilts), eyes (look + blink
// inside the tilting head group), core (brightness/glow pulse, never moved).
// This is NOT the abandoned layered-SVG recreation and NOT the flat cutout:
// at rest the six layers composite back to the original cutout (verified on
// the build machine: over the dark hero background only 27 of 2,560,000
// pixels differ by more than 10/255, max 26.6 — visually identical).
// White glossy body, dark face screen only, proper waving arm and hands,
// orange core, orange-tipped antenna — the artwork itself is unchanged.
// With reduced motion, no animation classes are applied and the mascot is
// static. Keyframes live in frontend/app/globals.css.
export function Mascot({ size = "large", className }: { size?: MascotSize; className?: string }) {
  const reduceMotion = useReducedMotion()
  const dims = SIZES[size]
  const a = (cls: string) => (reduceMotion ? "" : cls)
  const outer = className ? className + " " + a("mascot-bob") : a("mascot-bob")
  const layerStyle = {
    position: "absolute" as const,
    inset: 0,
    width: dims.width,
    height: dims.height,
    objectFit: "contain" as const,
    background: "transparent",
  }
  return (
    <div
      className={outer}
      style={{ position: "relative", width: dims.width, height: dims.height, background: "transparent" }}
      role="img"
      aria-label={ALT}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/mascot/body.webp" alt="" width={dims.width} height={dims.height} data-layer="body" style={layerStyle} />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/mascot/core.webp"
        alt=""
        width={dims.width}
        height={dims.height}
        data-layer="core"
        className={a("mascot-core")}
        style={layerStyle}
      />
      <div data-part="sway-arm" className={a("mascot-sway-arm")} style={layerStyle}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/mascot/sway.webp" alt="" width={dims.width} height={dims.height} data-layer="sway" style={layerStyle} />
      </div>
      <div data-part="wave-arm" className={a("mascot-wave")} style={layerStyle}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/mascot/wave.webp" alt="" width={dims.width} height={dims.height} data-layer="wave" style={layerStyle} />
      </div>
      <div data-part="head" className={a("mascot-tilt")} style={layerStyle}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/mascot/head.webp" alt="" width={dims.width} height={dims.height} data-layer="head" style={layerStyle} />
        <div data-part="eyes-look" className={a("mascot-look")} style={layerStyle}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/mascot/eyes.webp"
            alt=""
            width={dims.width}
            height={dims.height}
            data-layer="eyes"
            className={a("mascot-blink")}
            style={layerStyle}
          />
        </div>
      </div>
    </div>
  )
}
