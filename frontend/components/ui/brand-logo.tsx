'use client'

export interface BrandLogoProps {
  className?: string
  size?: number
  showWordmark?: boolean
  wordmarkClassName?: string
  showBadge?: boolean
  /**
   * Colour variant of the dot mark. 'dark' is the default: the component
   * is used on a dark UI, so the R dots are paper (#f5f2ea) and the field
   * dots are dark stone (#4a463f). 'light' is for light backgrounds: ink
   * R dots (#1b1b18) and light-stone field dots (#d8d2c4). The final
   * point is flat orange (#f26625) in both variants.
   */
  variant?: 'dark' | 'light'
}

// C1 Original: a flat dot-grid R on a 5x5 grid, viewBox 0 0 64 64,
// coordinates 12, 22, 32, 42, 52 on both axes. Flat colours only.
// The leg steps diagonally from (42,42) to the orange final point (52,52).
const FIELD_DOTS: ReadonlyArray<readonly [number, number]> = [
  [52, 12],
  [22, 22], [32, 22], [52, 22],
  [52, 32],
  [22, 42], [32, 42], [52, 42],
  [22, 52], [32, 52], [42, 52],
]

const R_DOTS: ReadonlyArray<readonly [number, number]> = [
  [12, 12], [22, 12], [32, 12], [42, 12],
  [12, 22], [42, 22],
  [12, 32], [22, 32], [32, 32], [42, 32],
  [12, 42], [42, 42],
  [12, 52],
]

export function BrandLogo({
  className = '',
  size = 34,
  showWordmark = false,
  wordmarkClassName = '',
  showBadge = false,
  variant = 'dark',
}: BrandLogoProps) {
  const rFill = variant === 'light' ? '#1b1b18' : '#f5f2ea'
  const fieldFill = variant === 'light' ? '#d8d2c4' : '#4a463f'

  return (
    <div className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="shrink-0"
        role="img"
        aria-label="RasoSynthTune"
      >
        {FIELD_DOTS.map(([cx, cy]) => (
          <circle key={`f-${cx}-${cy}`} cx={cx} cy={cy} r={2.6} fill={fieldFill} />
        ))}
        {R_DOTS.map(([cx, cy]) => (
          <circle key={`r-${cx}-${cy}`} cx={cx} cy={cy} r={3.6} fill={rFill} />
        ))}
        <circle cx={52} cy={52} r={3.6} fill="#f26625" />
      </svg>

      {showWordmark && (
        <div className="flex items-center gap-1.5">
          <span className={`font-display font-bold tracking-[-0.04em] text-white leading-none ${wordmarkClassName}`}>
            Raso<span className="text-[#f26625]">Synth</span><span className="text-[#d8d2c4] font-semibold">Tune</span>
          </span>
          {showBadge && (
            <span className="px-1.5 py-0.5 text-xs font-mono font-bold tracking-wider text-[#f26625] bg-[#f26625]/10 border border-[#f26625]/25 rounded">
              2.0
            </span>
          )}
        </div>
      )}
    </div>
  )
}

export default BrandLogo
