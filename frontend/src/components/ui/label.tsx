import { forwardRef, type LabelHTMLAttributes } from 'react'
import * as LabelPrimitive from '@radix-ui/react-label'

import { cn } from '@/lib/utils'

export const Label = forwardRef<
  HTMLLabelElement,
  LabelHTMLAttributes<HTMLLabelElement> & React.ComponentProps<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn('text-sm font-medium text-text peer-disabled:cursor-not-allowed peer-disabled:opacity-60', className)}
    {...props}
  />
))
Label.displayName = 'Label'
