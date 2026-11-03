import * as React from 'react'

/**
 * MetricCard — one dashboard metric rendered in a clean, frameless, unboxed presentation.
 * A metric is either a real backend value (value + source) or an honest
 * unknown state. It never renders a hardcoded, placeholder, or estimated
 * number as if it were measured.
 */
export type MetricState = 'ok' | 'unknown' | 'error'

export function MetricCard({
  label,
  value,
  source,
  state,
  note,
}: {
  label: string
  /** Rendered only when state === 'ok'. */
  value?: React.ReactNode
  /** Backend endpoint the value came from, e.g. '/api/quality/overview'. */
  source?: string
  state: MetricState
  /** Plain-language explanation for unknown/error states. */
  note?: string
}) {
  return (
    <div className="py-3 px-1 bg-transparent">
      <div className="font-mono text-xs font-bold uppercase tracking-wider text-[#a8a29e]">{label}</div>
      {state === 'ok' ? (
        <div className="mt-2 font-display text-2xl font-bold text-white">{value}</div>
      ) : (
        <div className="mt-2 font-mono text-sm font-bold text-[#d8d2c4]">Unknown</div>
      )}
      {state === 'ok' && source ? (
        <div className="mt-1 font-mono text-xs text-[#a8a29e]">Source: {source}</div>
      ) : null}
      {state !== 'ok' && note ? (
        <div className="mt-1 text-xs leading-relaxed text-[#a8a29e]">{note}</div>
      ) : null}
    </div>
  )
}
