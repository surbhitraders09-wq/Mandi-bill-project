import { useQuery } from '@tanstack/react-query'
import { Activity, Cpu, FileText, Users } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'

function Kpi({
  label,
  icon: Icon,
  value,
  loading,
  hint,
}: {
  label: string
  icon: typeof Activity
  value: string
  loading: boolean
  hint?: string
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted">{label}</CardTitle>
        <Icon className="h-4 w-4 text-muted" />
      </CardHeader>
      <CardContent>
        {loading ? <Skeleton className="h-8 w-24" /> : <p className="text-2xl font-semibold">{value}</p>}
        {hint && <CardDescription className="text-xs">{hint}</CardDescription>}
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const user = useAuthStore((s) => s.user)

  const automation = useQuery({
    queryKey: ['automation-state'],
    queryFn: () => api<{ status?: string; running?: boolean; last_run?: string }>('/api/automation/state'),
    refetchInterval: 15_000,
  })
  const bills = useQuery({
    queryKey: ['bills'],
    queryFn: () => api<{ items?: unknown[] }>('/api/bills?limit=5'),
  })
  const logs = useQuery({
    queryKey: ['logs'],
    queryFn: () => api<{ items?: unknown[] }>('/api/logs?limit=5'),
  })

  const automationStatus = automation.data?.status ?? 'idle'
  const automationRunning = automation.data?.running ?? false

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted">
          Welcome back, {user?.full_name ?? user?.username}. Here is the current market state.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          label="Bills today"
          icon={FileText}
          value={String(bills.data?.items?.length ?? 0)}
          loading={bills.isLoading}
          hint="Latest bills"
        />
        <Kpi
          label="Log entries"
          icon={Activity}
          value={String(logs.data?.items?.length ?? 0)}
          loading={logs.isLoading}
          hint="Latest log entries"
        />
        <Kpi
          label="Automation"
          icon={Cpu}
          value={automationRunning ? 'Running' : automationStatus}
          loading={automation.isLoading}
        />
        <Kpi label="Users" icon={Users} value="1" loading={false} hint="Local office" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent bills</CardTitle>
          </CardHeader>
          <CardContent>
            {bills.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : bills.data?.items?.length ? (
              <ul className="divide-y divide-border text-sm">
                {(bills.data.items as { id: number; farmer_name?: string; amount?: number }[]).map((b) => (
                  <li key={b.id} className="flex items-center justify-between py-2">
                    <span>{b.farmer_name ?? `Bill #${b.id}`}</span>
                    <span className="text-muted">{b.amount ? `₹${b.amount}` : ''}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="py-6 text-center text-sm text-muted">No bills recorded yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Automation status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2 text-sm">
              <p>
                Status: <span className="font-medium">{automationStatus}</span>
              </p>
              <p>
                Last run: <span className="font-medium">{automation.data?.last_run ?? '—'}</span>
              </p>
              <p className="text-xs text-muted">
                The automation agent syncs the market portal. Deep operations land in Phase 3.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
