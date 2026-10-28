import * as React from 'react'
import { clsx } from 'clsx'

/** SectionHeader — h2 in Manrope (display font is page titles only). */
export function SectionHeader({
  title,
  description,
  action,
  className,
}: {
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div className={clsx('flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between', className)}>
      <div>
        <h2 className="text-base font-semibold tracking-tight text-white">{title}</h2>
        {description ? <p className="mt-0.5 text-sm text-[#94a3b8]">{description}</p> : null}
      </div>
      {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
    </div>
  )
}
