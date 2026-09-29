import { type LucideIcon } from 'lucide-react'
import { Construction } from 'lucide-react'

export function PagePlaceholder({
  title,
  description,
  icon: Icon = Construction,
  phase = 'Phase 1',
}: {
  title: string
  description: string
  icon?: LucideIcon
  phase?: string
}) {
  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="text-sm text-muted">{description}</p>
      </div>
      <div className="flex flex-col items-center justify-center gap-3 rounded-md border border-dashed border-border py-20 text-center">
        <Icon className="h-8 w-8 text-muted" />
        <p className="text-sm font-medium text-text">{title}</p>
        <p className="max-w-sm text-sm text-muted">
          This module is part of {phase}. The frame is ready — functionality lands with its backend phase.
        </p>
      </div>
    </div>
  )
}
