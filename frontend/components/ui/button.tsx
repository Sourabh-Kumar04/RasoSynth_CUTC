import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'

const buttonVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-md text-xs sm:text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#008ecc] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-[#008ecc] text-white hover:bg-[#00a4eb] border border-[#0077ab] shadow-sm font-semibold glow-cerulean active:scale-[0.98]',
        cerulean: 'bg-[#008ecc] text-white hover:bg-[#00a4eb] border border-[#0077ab] shadow-sm font-semibold glow-cerulean active:scale-[0.98]',
        neon: 'bg-[#ff0038] text-white hover:bg-[#ff2654] border border-[#cc002d] shadow-sm font-bold glow-neon-red active:scale-[0.98]',
        destructive: 'bg-[#ff0038] text-white hover:bg-[#ff2654] border border-[#cc002d] shadow-sm font-bold glow-neon-red active:scale-[0.98]',
        outline: 'border border-[#1e2235] bg-[#090a0f] hover:bg-[#0f111a] hover:border-[#008ecc]/40 text-[#f4f6fa] shadow-2xs active:scale-[0.98]',
        secondary: 'bg-[#0c0d14] text-[#f4f6fa] hover:bg-[#12141e] border border-[#1e2235] active:scale-[0.98]',
        ghost: 'hover:bg-[#0f111a] text-[#f4f6fa]',
        link: 'text-[#008ecc] underline-offset-4 hover:underline hover:text-[#00a4eb]',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 rounded-md px-3 text-xs',
        lg: 'h-10 rounded-md px-5 text-sm',
        icon: 'h-8 w-8 rounded-md',
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
