import * as React from 'react'
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'
import { clsx } from 'clsx'
import type { StatusTone } from '@/lib/design-tokens'

const TONE: Record<
  StatusTone,
  { dot: string; text: string; border: string; bg: string; Icon: React.ComponentType<{ className?: string }> }
> = {
  ok: { dot: 'bg-emerald-400', text: 'text-emerald-400', border: 'border-emerald-500/30', bg: 'bg-emerald-500/10', Icon: CheckCircle2 },
  warn: { dot: 'bg-amber-400', text: 'text-amber-400', border: 'border-amber-500/30', bg: 'bg-amber-500/10', Icon: AlertTriangle },
  bad: { dot: 'bg-rose-400', text: 'text-rose-400', border: 'border-rose-500/30', bg: 'bg-rose-500/10', Icon: XCircle },
  neutral: { dot: 'bg-slate-400', text: 'text-slate-300', border: 'border-[#272738]', bg: 'bg-[#161622]', Icon: Info },
}

export type StatusItem = {
  /** Short label, always rendered as text — never colour-only. */
  label: string
  /** Plain-language qualifier, e.g. "placeholder, not production weights". */
  qualifier?: string
  tone: StatusTone
}

/**
 * StatusStrip — status as layout: text + icon + colour, at the page header
 * and on the panel it qualifies. Honest labels (SIMULATED / DEMO /
 * DEGRADED / ESTIMATED) live here, never in a footer alone.
 */
export function StatusStrip({ items, className }: { items: StatusItem[]; className?: string }) {
  if (items.length === 0) return null
  return (
    <div className={clsx('flex flex-wrap items-center gap-2', className)} role="status">
      {items.map((item) => {
        const t = TONE[item.tone]
        const Icon = t.Icon
        return (
          <span
            key={item.label}
            className={clsx('inline-flex items-center gap-1.5 rounded-sm border px-2.5 py-1 font-mono text-xs font-bold', t.border, t.bg, t.text)}
          >
            <span className={clsx('h-2 w-2 shrink-0 rounded-full', t.dot)} aria-hidden="true" />
            <Icon className="h-3.5 w-3.5 shrink-0" />
            {item.label}
            {item.qualifier ? <span className="font-sans font-normal text-[#94a3b8]">{item.qualifier}</span> : null}
          </span>
        )
      })}
    </div>
  )
}
