import { useQuery } from '@tanstack/react-query'
import { createColumnHelper, type ColumnDef } from '@tanstack/react-table'
import { useMemo } from 'react'
import { SmartTable } from '@/components/data/smart-table'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'

interface AuditEntry {
  id: number
  level: string
  message: string
  details?: string | null
  created_at: string
}

const columnHelper = createColumnHelper<AuditEntry>()

export function AuditPage() {
  const audit = useQuery({
    queryKey: ['audit'],
    queryFn: () => api<{ items: AuditEntry[] }>('/api/v1/audit?limit=200'),
    refetchInterval: 15_000,
  })

  const columns = useMemo<ColumnDef<AuditEntry, any>[]>(
    () => [
      columnHelper.accessor('id', { header: 'ID', size: 60 }),
      columnHelper.accessor('level', {
        header: 'Level',
        cell: (info) => {
          const level = info.getValue() ?? 'INFO'
          const variant =
            level === 'ERROR' ? 'danger' : level === 'WARNING' ? 'warning' : level === 'AUDIT' ? 'info' : 'default'
          return <Badge variant={variant}>{level}</Badge>
        },
      }),
      columnHelper.accessor('message', { header: 'Message', cell: (info) => info.getValue() }),
      columnHelper.accessor('details', {
        header: 'Details',
        cell: (info) => {
          const v = info.getValue()
          if (typeof v === 'string') return <span className="text-muted">{v}</span>
          if (v && typeof v === 'object') return <span className="text-muted">{JSON.stringify(v)}</span>
          return <span className="text-muted">—</span>
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
        <h1 className="text-2xl font-semibold">Activity Log</h1>
        <p className="text-sm text-muted">Server log entries including authentication and audit events.</p>
      </div>
      <SmartTable<AuditEntry>
        columns={columns}
        data={audit.data?.items ?? []}
        loading={audit.isLoading}
        searchPlaceholder="Search log entries…"
        exportName="audit-log"
      />
    </div>
  )
}
