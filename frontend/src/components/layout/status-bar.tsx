import { useEffect, useState } from 'react'
import { Circle, RefreshCw } from 'lucide-react'

import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { cn } from '@/lib/utils'

interface AutomationState {
  status?: string
  running?: boolean
  last_run?: string | null
  next_run?: string | null
}

function useAutomationState() {
  const [state, setState] = useState<AutomationState | null>(null)
  const [online, setOnline] = useState(true)
  const user = useAuthStore((s) => s.user)

  useEffect(() => {
    if (!user) return
    let alive = true
    const tick = async () => {
      try {
        const data = await api<AutomationState>('/api/automation/state')
        if (alive) {
          setState(data)
          setOnline(true)
        }
      } catch {
        if (alive) setOnline(false)
      }
    }
    tick()
    const t = setInterval(tick, 10_000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [user])

  return { state, online }
}

export function StatusBar() {
  const { state, online } = useAutomationState()
  const user = useAuthStore((s) => s.user)

  const running = state?.running ?? false

  return (
    <footer className="flex h-7 items-center gap-4 border-t border-border bg-surface px-4 text-xs text-muted">
      <span className="flex items-center gap-1.5">
        <Circle className={cn('h-2 w-2', running ? 'fill-primary text-primary' : 'text-success')} />
        Automation {running ? 'running' : state ? state.status ?? 'idle' : '…'}
      </span>
      <span className="flex items-center gap-1.5">
        <RefreshCw className="h-3 w-3" />
        {online ? 'API online' : 'API offline'}
      </span>
      <span className="ml-auto hidden sm:inline">
        {user ? `${user.full_name ?? user.username} · ${user.role}` : 'Not signed in'}
      </span>
    </footer>
  )
}
