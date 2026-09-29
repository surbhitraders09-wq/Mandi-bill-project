import { forwardRef, type InputHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-text placeholder:text-muted focus-visible:outline-2 focus-visible:outline-info disabled:cursor-not-allowed disabled:opacity-60',
        className,
      )}
      {...props}
    />
  ),
)
Input.displayName = 'Input'
