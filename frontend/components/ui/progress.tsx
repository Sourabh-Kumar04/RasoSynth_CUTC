import * as React from 'react'
import * as ProgressPrimitive from '@radix-ui/react-progress'
import { clsx } from 'clsx'

const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root>
>(({ className, value, ...props }, ref) => (
  <ProgressPrimitive.Root
    ref={ref}
    className={clsx(
      'relative h-2 w-full overflow-hidden rounded-full bg-[#0c0d14] border border-[#1e2235]',
      className
    )}
    {...props}
  >
    <ProgressPrimitive.Indicator
      className="h-full w-full flex-1 bg-[#008ecc] shadow-[0_0_12px_rgba(0,142,204,0.6)] transition-all duration-300 rounded-sm"
      style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
    />
  </ProgressPrimitive.Root>
))
Progress.displayName = ProgressPrimitive.Root.displayName

export { Progress }
