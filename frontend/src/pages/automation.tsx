import { useQuery } from '@tanstack/react-query'
import { Cpu, ListChecks, Play, RefreshCw, Square, XCircle } from 'lucide-react'
import { useState } from 'react'

import { StatCard } from '@/components/data/stat-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { api } from '@/lib/api'
import { searchTodayBills, getState } from '@/lib/mobile'
import { toast } from '@/lib/toast'
import { cn } from '@/lib/utils'

interface AutomationState {
  state: string
  busy: boolean
  found_bills: number
  current_bill_id?: number | null
  show_captcha: boolean
  progress: string
  progress_events: { ts: string; message: string }[]
}

const STATE_BADGE: Record<string, 'default' | 'success' | 'warning' | 'danger' | 'info'> = {
  idle: 'default',
  searching: 'info',
  awaiting_captcha: 'warning',
  bills_loaded: 'success',
  bill_selected: 'success',
  ready_to_print: 'info',
  printing: 'warning',
  error: 'danger',
}

export function AutomationPage() {
  const [running, setRunning] = useState<string | null>(null)

  const state = useQuery({
    queryKey: ['automation-state'],
    queryFn: () => api<AutomationState>('/api/automation/state'),
    refetchInterval: 3_000,
  })

  const st = state.data ?? ({} as Partial<AutomationState>)

  async function runToday() {
    setRunning('today')
    try {
      const res = await searchTodayBills()
      toast.success('Today bills loaded', `${res.bills.length} bills found`)
    } catch (err) {
      toast.error('Search failed', err instanceof Error ? err.message : undefined)
    } finally {
      setRunning(null)
      state.refetch()
    }
  }

  async function cancel() {
    try {
      await api('/api/automation/cancel', { method: 'POST' })
      toast.info('Cancelled', 'Automation stopped')
      state.refetch()
    } catch (err) {
      toast.error('Cancel failed', err instanceof Error ? err.message : undefined)
    }
  }

  async function refresh() {
    setRunning('refresh')
    try {
      await getState()
      toast.success('State refreshed')
    } finally {
      setRunning(null)
      state.refetch()
    }
  }

  const badgeVariant = STATE_BADGE[st.state ?? 'idle'] ?? 'muted'
  const busy = st.busy ?? false

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Automation</h1>
          <p className="text-sm text-muted">Inspect and drive the e-Mandi portal automation agent.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={refresh} disabled={running !== null}>
            <RefreshCw className="mr-2 h-4 w-4" /> Refresh
          </Button>
          <Button onClick={runToday} disabled={running !== null || busy}>
            <Play className="mr-2 h-4 w-4" /> Load today&apos;s bills
          </Button>
          <Button variant="danger" onClick={cancel} disabled={running !== null || !busy}>
            <Square className="mr-2 h-4 w-4" /> Cancel
          </Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="State"
          icon={<Cpu className="h-4 w-4" />}
          value={<Badge variant={badgeVariant}>{st.state ?? '…'}</Badge>}
          loading={state.isLoading}
        />
        <StatCard
          label="Busy"
          icon={<ListChecks className="h-4 w-4" />}
          value={busy ? 'Yes' : 'No'}
          loading={state.isLoading}
        />
        <StatCard
          label="Bills found"
          icon={<ListChecks className="h-4 w-4" />}
          value={String(st.found_bills ?? 0)}
          loading={state.isLoading}
        />
        <StatCard
          label="Current bill"
          icon={<Cpu className="h-4 w-4" />}
          value={st.current_bill_id != null ? `#${st.current_bill_id}` : '—'}
          loading={state.isLoading}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Progress</CardTitle>
          <CardDescription>Live state from the automation agent.</CardDescription>
        </CardHeader>
        <CardContent>
          {state.isLoading ? (
            <p className="text-sm text-muted">Loading state…</p>
          ) : st.progress ? (
            <p className="flex items-center gap-2 text-sm">
              {busy && (
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
              )}
              <span className={cn(busy && 'text-primary')}>{st.progress}</span>
            </p>
          ) : (
            <p className="text-sm text-muted">Agent is idle.</p>
          )}

          {(st.progress_events?.length ?? 0) > 0 && (
            <div className="mt-4 max-h-64 space-y-1 overflow-y-auto rounded-md border border-border bg-bg p-3">
              {st.progress_events?.map((ev, i) => (
                <div key={i} className="flex gap-2 text-xs">
                  <span className="shrink-0 font-mono text-muted">{ev.ts}</span>
                  <span>{ev.message}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Actions</CardTitle>
          <CardDescription>Portal automation workflows.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button onClick={runToday} disabled={busy}>
            <Play className="mr-2 h-4 w-4" /> Search today&apos;s bills
          </Button>
          <Button variant="danger" onClick={cancel} disabled={!busy}>
            <XCircle className="mr-2 h-4 w-4" /> Cancel running task
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
