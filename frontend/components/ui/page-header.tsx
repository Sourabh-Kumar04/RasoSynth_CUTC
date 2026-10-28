import * as React from 'react'
import { clsx } from 'clsx'

/**
 * PageHeader — the one page-opening contract.
 * Every page opens: eyebrow -> title (Bodoni Moda) -> one-line purpose ->
 * primary action -> status strip. Status is layout, never a footnote.
 */
export function PageHeader({
  eyebrow,
  title,
  purpose,
  action,
  status,
  className,
}: {
  eyebrow: string
  title: string
  purpose: string
  action?: React.ReactNode
  status?: React.ReactNode
  className?: string
}) {
  return (
    <div className={clsx('border-b border-[#272738] pb-4', className)}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2.5">
            <span className="rounded-sm border border-[#f26625]/30 bg-[#f26625]/10 px-2 py-0.5 font-mono text-xs font-bold uppercase tracking-wider text-[#f26625]">
              {eyebrow}
            </span>
          </div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-white">{title}</h1>
          <p className="mt-1 text-sm text-[#94a3b8]">{purpose}</p>
        </div>
        {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
      </div>
      {status ? <div className="mt-3">{status}</div> : null}
    </div>
  )
}
