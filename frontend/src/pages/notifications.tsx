import { useQuery } from '@tanstack/react-query'
import { createColumnHelper, type ColumnDef } from '@tanstack/react-table'
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'
import { useMemo } from 'react'

import { SmartTable } from '@/components/data/smart-table'
import { StatCard } from '@/components/data/stat-card'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'

interface LogEntry {
  id: number
  level: string
  message: string
  details?: unknown
  created_at: string
}

const columnHelper = createColumnHelper<LogEntry>()

function LevelIcon({ level }: { level: string }) {
  const l = level.toUpperCase()
  if (l === 'ERROR') return <XCircle className="h-3 w-3" />
  if (l === 'WARNING') return <AlertTriangle className="h-3 w-3" />
  if (l === 'SUCCESS') return <CheckCircle2 className="h-3 w-3" />
  return <Info className="h-3 w-3" />
}

function variantFor(level: string): 'default' | 'success' | 'warning' | 'danger' | 'info' | 'muted' {
  const l = level.toUpperCase()
  if (l === 'ERROR') return 'danger'
  if (l === 'WARNING') return 'warning'
  if (l === 'SUCCESS') return 'success'
  if (l === 'INFO') return 'info'
  return 'muted'
}

export function NotificationsPage() {
  const logs = useQuery({
    queryKey: ['logs', 'notifications'],
    queryFn: () => api<{ items: LogEntry[]; total: number }>('/api/logs?limit=200'),
    refetchInterval: 15_000,
  })

  const items = logs.data?.items ?? []
  const errors = items.filter((l) => l.level?.toUpperCase() === 'ERROR').length
  const warnings = items.filter((l) => l.level?.toUpperCase() === 'WARNING').length
  const successes = items.filter((l) => l.level?.toUpperCase() === 'SUCCESS').length
  const infos = items.length - errors - warnings - successes

  const columns = useMemo<ColumnDef<LogEntry, any>[]>(
    () => [
      columnHelper.accessor('id', { header: 'ID', size: 70 }),
      columnHelper.accessor('level', {
        header: 'Level',
        cell: (info) => (
          <Badge variant={variantFor(info.getValue() ?? 'INFO')}>
            <LevelIcon level={info.getValue() ?? 'INFO'} />
            {(info.getValue() ?? 'INFO').toUpperCase()}
          </Badge>
        ),
      }),
      columnHelper.accessor('message', {
        header: 'Message',
        cell: (info) => (
          <span className="line-clamp-2 max-w-[480px]">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor('details', {
        header: 'Details',
        cell: (info) => {
          const v = info.getValue()
          if (v == null) return <span className="text-muted">—</span>
          if (typeof v === 'string') return <span className="line-clamp-2 max-w-[240px] text-xs text-muted">{v}</span>
          if (typeof v === 'object') return <span className="line-clamp-2 max-w-[240px] text-xs text-muted">{JSON.stringify(v)}</span>
          return <span className="text-muted">{String(v)}</span>
        },
      }),
      columnHelper.accessor('created_at', {
        header: 'Time',
        cell: (info) => new Date(info.getValue() as string).toLocaleString(),
      }),
    ],
    [],
  )

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Notifications</h1>
        <p className="text-sm text-muted">Payment alerts, errors, and system events.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Alerts (errors)"
          icon={<XCircle className="h-4 w-4" />}
          value={String(errors)}
          hint="system errors"
          loading={logs.isLoading}
        />
        <StatCard
          label="Warnings"
          icon={<AlertTriangle className="h-4 w-4" />}
          value={String(warnings)}
          loading={logs.isLoading}
        />
        <StatCard
          label="Success"
          icon={<CheckCircle2 className="h-4 w-4" />}
          value={String(successes)}
          loading={logs.isLoading}
        />
        <StatCard
          label="Info"
          icon={<Info className="h-4 w-4" />}
          value={String(infos)}
          hint="last 200 events"
          loading={logs.isLoading}
        />
      </div>

      <SmartTable<LogEntry>
        columns={columns}
        data={items}
        loading={logs.isLoading}
        searchPlaceholder="Search notifications…"
        exportName="notifications"
        filterKey="notifications-list"
      />
    </div>
  )
}
