import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

const badgeVariants = cva(
  'inline-flex items-center rounded-sm border px-2.5 py-0.5 text-[11px] font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-[#008ecc] focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-[#0077ab] bg-[#008ecc] text-white shadow-xs',
        cerulean: 'border-[#008ecc]/35 bg-[#008ecc]/12 text-[#00a4eb]',
        neon: 'border-[#ff0038]/35 bg-[#ff0038]/12 text-[#ff0038]',
        secondary: 'border-[#1e2235] bg-[#0c0d14] text-[#f4f6fa]',
        destructive: 'border-[#ff0038]/40 bg-[#ff0038]/15 text-[#ff0038]',
        success: 'border-emerald-500/30 bg-emerald-950/40 text-emerald-400',
        warning: 'border-amber-500/30 bg-amber-950/40 text-amber-400',
        outline: 'text-[#f4f6fa] border-[#1e2235] bg-[#090a0f]',
        dot: 'border-transparent bg-transparent',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={clsx(badgeVariants({ variant }), className)} {...props} />
}

// Status badge with dot indicator
const statusColors = {
  healthy: 'bg-emerald-500',
  degraded: 'bg-amber-500',
  unhealthy: 'bg-[#ff0038]',
  disabled: 'bg-slate-400',
  running: 'bg-[#008ecc] animate-pulse',
  pending: 'bg-amber-500',
  completed: 'bg-emerald-600',
  failed: 'bg-[#ff0038]',
  cancelled: 'bg-slate-400',
}

const StatusBadge = ({
  status,
  label,
  className,
}: {
  status: string
  label?: string
  className?: string
}) => {
  const colorClass = statusColors[status as keyof typeof statusColors] || 'bg-slate-400'

  return (
    <div className={clsx('inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-sm bg-[#0c0d14] border border-[#1e2235]', className)}>
      <span className={clsx('h-2 w-2 rounded-full', colorClass)} />
      <span className="text-[11px] font-mono font-medium text-[#00a4eb] capitalize">{label || status}</span>
    </div>
  )
}

export { Badge, badgeVariants, StatusBadge, statusColors }
