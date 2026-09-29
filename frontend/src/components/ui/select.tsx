import { forwardRef, type SelectHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

export interface SelectOption {
  value: string
  label: string
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  options: SelectOption[]
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, options, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        'h-10 w-full cursor-pointer rounded-md border border-border bg-surface px-3 text-sm text-text focus-visible:outline-2 focus-visible:outline-info disabled:cursor-not-allowed disabled:opacity-60',
        className,
      )}
      {...props}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  ),
)
Select.displayName = 'Select'
