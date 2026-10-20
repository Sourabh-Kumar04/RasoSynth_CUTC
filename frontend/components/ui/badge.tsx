import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

const badgeVariants = cva(
  'inline-flex items-center rounded-sm border px-2.5 py-0.5 text-[11px] font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-[#f26625] focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-[#ea580c] bg-[#f26625] text-white',
        secondary: 'border-[#272738] bg-[#161622] text-[#f8fafc]',
        destructive: 'border-rose-500/30 bg-rose-950/40 text-rose-400',
        success: 'border-emerald-500/30 bg-emerald-950/40 text-emerald-400',
        warning: 'border-amber-500/30 bg-amber-950/40 text-amber-400',
        outline: 'text-[#f8fafc] border-[#272738] bg-[#161622]',
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
  unhealthy: 'bg-rose-500',
  disabled: 'bg-slate-400',
  running: 'bg-emerald-500 animate-pulse',
  pending: 'bg-amber-500',
  completed: 'bg-emerald-600',
  failed: 'bg-rose-500',
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
    <div className={clsx('inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-sm bg-[#161622] border border-[#272738]', className)}>
      <span className={clsx('h-2 w-2 rounded-full', colorClass)} />
      <span className="text-[11px] font-mono font-medium text-[#f26625] capitalize">{label || status}</span>
    </div>
  )
}

export { Badge, badgeVariants, StatusBadge, statusColors }
