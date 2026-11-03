import * as React from 'react'
import { clsx } from 'clsx'

function cleanBoxCardClasses(className?: string): string {
  if (!className) return ''
  return className
    .replace(/\bborder(-[#a-zA-Z0-9_/]+)?\b/g, '')
    .replace(/\bbg-\[#12121a\](\/[0-9]+)?\b/g, '')
    .replace(/\bbg-surface\b/g, '')
    .replace(/\bcard-shadow\b/g, '')
    .replace(/\brounded(-md|-lg|-xl|-2xl)?\b/g, '')
    .replace(/\bglow-card-hover\b/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={clsx(
        'bg-transparent text-[#f5f2ea] border-0 shadow-none',
        cleanBoxCardClasses(className)
      )}
      {...props}
    />
  )
)
Card.displayName = 'Card'

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={clsx('flex flex-col space-y-1.5 pb-3 border-0', cleanBoxCardClasses(className))}
      {...props}
    />
  )
)
CardHeader.displayName = 'CardHeader'

const CardTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3
      ref={ref}
      className={clsx('font-semibold text-lg leading-tight tracking-tight text-[#f5f2ea]', className)}
      {...props}
    />
  )
)
CardTitle.displayName = 'CardTitle'

const CardDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p
      ref={ref}
      className={clsx('text-xs sm:text-sm text-muted-foreground', className)}
      {...props}
    />
  )
)
CardDescription.displayName = 'CardDescription'

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={clsx('pt-0 border-0', cleanBoxCardClasses(className))} {...props} />
  )
)
CardContent.displayName = 'CardContent'

const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={clsx('flex items-center pt-3 border-0', cleanBoxCardClasses(className))}
      {...props}
    />
  )
)
CardFooter.displayName = 'CardFooter'

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
