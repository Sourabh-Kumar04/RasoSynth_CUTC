import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-accent text-white',
        secondary: 'border-transparent bg-surface text-foreground',
        destructive: 'border-transparent bg-error text-white',
        success: 'border-transparent bg-success text-white',
        warning: 'border-transparent bg-warning text-white',
        outline: 'text-foreground border-border',
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
  healthy: 'bg-success',
  degraded: 'bg-warning',
  unhealthy: 'bg-error',
  disabled: 'bg-muted-foreground',
  running: 'bg-info',
  pending: 'bg-muted-foreground',
  completed: 'bg-success',
  failed: 'bg-error',
  cancelled: 'bg-muted-foreground',
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
  const colorClass = statusColors[status as keyof typeof statusColors] || 'bg-muted-foreground'

  return (
    <div className={clsx('inline-flex items-center gap-1.5', className)}>
      <span className={clsx('h-2 w-2 rounded-full', colorClass)} />
      <Badge variant="secondary">{label || status}</Badge>
    </div>
  )
}

export { Badge, badgeVariants, StatusBadge, statusColors }
