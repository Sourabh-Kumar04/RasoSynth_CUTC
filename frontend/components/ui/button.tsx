import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

const buttonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-lg text-xs sm:text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#FF7A1A] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-gradient-to-r from-[#FF7A1A] via-[#FF385C] to-[#C084FC] text-white hover:opacity-90 shadow-[0_2px_12px_rgba(255,122,26,0.3)] font-semibold active:scale-[0.98] border-0',
        destructive: 'bg-rose-600 text-white hover:bg-rose-700 shadow-sm active:scale-[0.98]',
        outline: 'border border-white/10 bg-white/[0.03] hover:bg-white/[0.08] text-white active:scale-[0.98]',
        secondary: 'bg-white/[0.06] text-white hover:bg-white/[0.1] active:scale-[0.98] border-0',
        ghost: 'hover:bg-white/[0.06] text-zinc-300 hover:text-white',
        link: 'text-[#FF7A1A] underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 rounded-lg px-3 text-xs',
        lg: 'h-10 rounded-xl px-5 text-sm',
        icon: 'h-8 w-8 rounded-lg',
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
