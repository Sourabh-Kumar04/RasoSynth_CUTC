"use client"

import Image from "next/image"
import { motion, useReducedMotion } from "framer-motion"

export type MascotSize = "large" | "medium"

const SIZES: Record<MascotSize, { width: number; height: number }> = {
  large: { width: 280, height: 280 },
  medium: { width: 160, height: 160 },
}

export function Mascot({ size = "large", className }: { size?: MascotSize; className?: string }) {
  const reduceMotion = useReducedMotion()
  const dims = SIZES[size]
  return (
    <motion.div
      className={className}
      initial={false}
      animate={reduceMotion ? undefined : { y: [0, -10, 0] }}
      transition={reduceMotion ? undefined : { duration: 5, repeat: Infinity, ease: "easeInOut" }}
    >
      <Image
        src="/mascot-robot.webp"
        alt="Raso, the RasoSynthTune assistant, a cute white robot with a glowing orange core, waving hello"
        width={dims.width}
        height={dims.height}
        priority={size === "large"}
      />
    </motion.div>
  )
}
