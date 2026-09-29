import { AlertCircle, CheckCircle2, Info, XCircle } from 'lucide-react'
import { useEffect } from 'react'

import { useToastStore, type ToastItem, type ToastKind } from '@/lib/toast'
import { cn } from '@/lib/utils'

const icons: Record<ToastKind, typeof Info> = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertCircle,
  info: Info,
}

const colors: Record<ToastKind, string> = {
  success: 'text-success',
  error: 'text-danger',
  warning: 'text-warning',
  info: 'text-info',
}

function ToastCard({ item }: { item: ToastItem }) {
  const dismiss = useToastStore((s) => s.dismiss)
  const Icon = icons[item.kind]

  useEffect(() => {
    const t = setTimeout(() => dismiss(item.id), 4500)
    return () => clearTimeout(t)
  }, [item.id, dismiss])

  return (
    <div
      role="status"
      className="pointer-events-auto flex w-full items-start gap-3 rounded-md border border-border bg-surface p-4 shadow-popover"
    >
      <Icon className={cn('mt-0.5 h-5 w-5 shrink-0', colors[item.kind])} />
      <div className="flex-1">
        <p className="text-sm font-medium text-text">{item.title}</p>
        {item.description && <p className="mt-0.5 text-sm text-muted">{item.description}</p>}
      </div>
      <button
        onClick={() => dismiss(item.id)}
        className="rounded-sm text-muted opacity-70 transition-opacity hover:opacity-100"
        aria-label="Dismiss notification"
      >
        <XCircle className="h-4 w-4" />
      </button>
    </div>
  )
}

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts)
  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="pointer-events-none fixed right-4 top-4 z-[60] flex w-full max-w-sm flex-col gap-2"
    >
      {toasts.map((t) => (
        <ToastCard key={t.id} item={t} />
      ))}
    </div>
  )
}
