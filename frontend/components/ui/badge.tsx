import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-3 py-0.5 text-[11px] font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-[#1B3B2B] focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-[#1B3B2B] text-white',
        secondary: 'border-transparent bg-[#E8ECE6] text-[#1B3B2B]',
        destructive: 'border-rose-200 bg-rose-50 text-rose-700',
        success: 'border-emerald-300 bg-emerald-50 text-emerald-800',
        warning: 'border-amber-300 bg-amber-50 text-amber-800',
        outline: 'text-[#1B3B2B] border-[#D1D8CE] bg-white',
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
    <div className={clsx('inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#E8ECE6] border border-[#D1D8CE]', className)}>
      <span className={clsx('h-2 w-2 rounded-full', colorClass)} />
      <span className="text-[11px] font-mono font-medium text-[#1B3B2B] capitalize">{label || status}</span>
    </div>
  )
}

export { Badge, badgeVariants, StatusBadge, statusColors }
