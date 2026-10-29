"use client"

import { useReducedMotion } from "framer-motion"

export type MascotSize = "large" | "medium"

const SIZES: Record<MascotSize, { width: number; height: number }> = {
  large: { width: 280, height: 280 },
  medium: { width: 160, height: 160 },
}

const ALT =
  "Raso, the RasoSynthTune assistant, a glossy white robot with a dark face screen, big sparkling eyes, an open smile, and a glowing orange core, waving hello"

// Layered SVG recreation of the STANDALONE white robot (user choice, 2026-10-29),
// NOT the cute robot and NOT the raw black-background raster. The raster cannot
// move its parts independently and its black background shows as a box on the
// dark hero, so the mascot is rebuilt here as separate SVG groups on a fully
// transparent background (no background rect, no backdrop fill): the waving
// arm rotates at the shoulder, the other arm sways, the head tilts, the eyes
// look side to side and blink, the core pulses, and the antenna bounces,
// while the whole mascot bobs. Keyframes live in frontend/app/globals.css.
// With reduced motion, no animation classes are applied and the mascot is static.
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
      <svg
        width={dims.width}
        height={dims.height}
        viewBox="0 0 280 280"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <title>{ALT}</title>
        <g className={a("mascot-antenna")} data-part="antenna">
          <line x1={140} y1={44} x2={140} y2={18} stroke="#f26625" strokeWidth={5} strokeLinecap="round" />
          <circle cx={140} cy={13} r={9} fill="#f26625" />
          <circle cx={137} cy={10} r={2.5} fill="#ffcf9e" />
        </g>
        <g className={a("mascot-wave")} data-part="wave-arm">
          <line x1={92} y1={190} x2={48} y2={148} stroke="#ffffff" strokeWidth={26} strokeLinecap="round" />
          <circle cx={40} cy={150} r={17} fill="#ffffff" stroke="#e7e2d6" strokeWidth={2} />
          <circle cx={28} cy={134} r={8} fill="#ffffff" />
          <circle cx={40} cy={126} r={8} fill="#ffffff" />
          <circle cx={52} cy={130} r={8} fill="#ffffff" />
        </g>
        <g className={a("mascot-sway")} data-part="sway-arm">
          <line x1={188} y1={190} x2={224} y2={234} stroke="#ffffff" strokeWidth={26} strokeLinecap="round" />
          <circle cx={228} cy={240} r={16} fill="#ffffff" stroke="#e7e2d6" strokeWidth={2} />
        </g>
        <rect x={82} y={166} width={116} height={92} rx={42} fill="#ffffff" stroke="#e7e2d6" strokeWidth={2} />
        <g className={a("mascot-pulse")} data-part="core">
          <circle cx={140} cy={208} r={27} fill="#f26625" opacity={0.16} />
          <circle cx={140} cy={208} r={18} fill="#f26625" />
          <circle cx={140} cy={208} r={9} fill="#ff9a5c" />
          <circle cx={134} cy={202} r={3} fill="#ffffff" opacity={0.8} />
        </g>
        <g className={a("mascot-tilt")} data-part="head">
          <circle cx={50} cy={102} r={17} fill="#ffffff" stroke="#e7e2d6" strokeWidth={2} />
          <circle cx={230} cy={102} r={17} fill="#ffffff" stroke="#e7e2d6" strokeWidth={2} />
          <rect x={58} y={40} width={164} height={118} rx={54} fill="#ffffff" stroke="#e7e2d6" strokeWidth={2} />
          <rect x={78} y={58} width={124} height={76} rx={30} fill="#1f1f24" />
          <g className={a("mascot-look")} data-part="eyes-look">
            <g className={a("mascot-blink")} data-part="eyes">
              <circle cx={116} cy={96} r={15} fill="#050505" stroke="#4a4a4a" strokeWidth={1} />
              <circle cx={111} cy={90} r={4} fill="#ffffff" />
              <circle cx={122} cy={100} r={2} fill="#ffffff" />
              <circle cx={122} cy={106} r={2} fill="#f26625" />
              <circle cx={164} cy={96} r={15} fill="#050505" stroke="#4a4a4a" strokeWidth={1} />
              <circle cx={159} cy={90} r={4} fill="#ffffff" />
              <circle cx={170} cy={100} r={2} fill="#ffffff" />
              <circle cx={170} cy={106} r={2} fill="#f26625" />
            </g>
          </g>
          <path
            d="M122 120 Q140 118 158 120 Q156 138 140 140 Q124 138 122 120 Z"
            fill="#1a0f12"
          />
          <ellipse cx={140} cy={134} rx={8} ry={4} fill="#b45a5a" />
        </g>
      </svg>
    </div>
  )
}
