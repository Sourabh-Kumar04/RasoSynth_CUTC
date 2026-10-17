import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

const buttonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-full text-xs sm:text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6366f1] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-[#6366f1] text-white hover:bg-[#4f46e5] shadow-sm font-semibold active:scale-[0.98]',
        destructive: 'bg-rose-600 text-white hover:bg-rose-700 shadow-sm active:scale-[0.98]',
        outline: 'border border-[#3b3b52] bg-[#12121a] hover:bg-[#161622] text-[#f8fafc] shadow-2xs active:scale-[0.98]',
        secondary: 'bg-[#161622] text-[#f8fafc] hover:bg-[#272738] border border-[#3b3b52] active:scale-[0.98]',
        ghost: 'hover:bg-[#161622] text-[#f8fafc]',
        link: 'text-[#6366f1] underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 rounded-full px-3.5 text-xs',
        lg: 'h-10 rounded-full px-6 text-sm',
        icon: 'h-9 w-9 rounded-full',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={clsx(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }
