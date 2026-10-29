"use client"

import { useReducedMotion } from "framer-motion"

export type MascotSize = "large" | "medium"

const SIZES: Record<MascotSize, { width: number; height: number }> = {
  large: { width: 280, height: 280 },
  medium: { width: 160, height: 160 },
}

const ALT =
  "Raso, the RasoSynthTune assistant, a cute white robot with a glowing orange core, waving hello"

// Layered animated mascot. The approved robot is rebuilt as separate SVG
// groups so each part can move on its own: the waving hand rotates at the
// shoulder, the other hand sways, the head tilts, the eyes blink, the core
// pulses, and the antenna bounces, while the whole mascot bobs. Keyframes
// live in frontend/app/globals.css. With reduced motion, no animation
// classes are applied and the mascot renders static.
export function Mascot({ size = "large", className }: { size?: MascotSize; className?: string }) {
  const reduceMotion = useReducedMotion()
  const dims = SIZES[size]
  const a = (cls: string) => (reduceMotion ? "" : cls)
  const outer = className ? className + " " + a("mascot-bob") : a("mascot-bob")
  return (
    <div
      className={outer}
      style={{ width: dims.width, height: dims.height }}
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
        <g className={a("mascot-antenna")}>
          <line x1={140} y1={44} x2={140} y2={18} stroke="#c9c2b2" strokeWidth={5} strokeLinecap="round" />
          <circle cx={140} cy={13} r={9} fill="#f26625" />
        </g>
        <g className={a("mascot-wave")}>
          <line x1={92} y1={190} x2={42} y2={142} stroke="#ffffff" strokeWidth={26} strokeLinecap="round" />
          <circle cx={36} cy={146} r={17} fill="#ffffff" stroke="#e7e2d6" strokeWidth={2} />
        </g>
        <g className={a("mascot-sway")}>
          <line x1={188} y1={190} x2={224} y2={234} stroke="#ffffff" strokeWidth={26} strokeLinecap="round" />
          <circle cx={228} cy={240} r={16} fill="#ffffff" stroke="#e7e2d6" strokeWidth={2} />
        </g>
        <rect x={82} y={166} width={116} height={92} rx={42} fill="#ffffff" stroke="#e7e2d6" strokeWidth={2} />
        <g className={a("mascot-pulse")}>
          <circle cx={140} cy={208} r={27} fill="#f26625" opacity={0.16} />
          <circle cx={140} cy={208} r={18} fill="#f26625" />
          <circle cx={140} cy={208} r={9} fill="#ff9a5c" />
          <circle cx={134} cy={202} r={3} fill="#ffffff" opacity={0.8} />
        </g>
        <g className={a("mascot-tilt")}>
          <circle cx={50} cy={102} r={17} fill="#ffffff" stroke="#e7e2d6" strokeWidth={2} />
          <circle cx={230} cy={102} r={17} fill="#ffffff" stroke="#e7e2d6" strokeWidth={2} />
          <rect x={58} y={40} width={164} height={118} rx={54} fill="#ffffff" stroke="#e7e2d6" strokeWidth={2} />
          <rect x={78} y={58} width={124} height={76} rx={30} fill="#1b1b18" />
          <g className={a("mascot-blink")}>
            <circle cx={116} cy={96} r={15} fill="#050505" stroke="#4a4a4a" strokeWidth={1} />
            <circle cx={111} cy={90} r={4} fill="#ffffff" />
            <circle cx={122} cy={100} r={2} fill="#ffffff" />
            <circle cx={164} cy={96} r={15} fill="#050505" stroke="#4a4a4a" strokeWidth={1} />
            <circle cx={159} cy={90} r={4} fill="#ffffff" />
            <circle cx={170} cy={100} r={2} fill="#ffffff" />
          </g>
          <path d="M124 122 Q140 131 156 122" stroke="#f5f2ea" strokeWidth={3.5} strokeLinecap="round" />
        </g>
      </svg>
    </div>
  )
}
