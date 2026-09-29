import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createColumnHelper, type ColumnDef } from '@tanstack/react-table'
import { Plus } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { SmartTable } from '@/components/data/smart-table'
import { TraderForm } from '@/components/forms/trader-form'
import { Permission } from '@/components/layout/permission'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import type { ListResponse, Trader } from '@/lib/types'

const columnHelper = createColumnHelper<Trader>()

export function TradersPage() {
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const traders = useQuery({
    queryKey: ['traders', debouncedQ],
    queryFn: () =>
      api<ListResponse<Trader>>(`/api/v1/traders?limit=500${debouncedQ ? `&q=${encodeURIComponent(debouncedQ)}` : ''}`),
  })

  const onSearch = () => setDebouncedQ(q.trim())

  const columns = useMemo<ColumnDef<Trader, any>[]>(
    () => [
      columnHelper.accessor('name', { header: 'Name', cell: (info) => info.getValue() }),
      columnHelper.accessor('gstin', { header: 'GSTIN', cell: (info) => info.getValue() ?? '—' }),
      columnHelper.accessor('pan', { header: 'PAN', cell: (info) => info.getValue() ?? '—' }),
      columnHelper.accessor('mobile', { header: 'Mobile', cell: (info) => info.getValue() ?? '—' }),
      columnHelper.accessor('commission_rate', {
        header: 'Commission',
        cell: (info) => `${info.getValue()}%`,
      }),
      columnHelper.accessor('created_at', {
        header: 'Registered',
        cell: (info) => {
          const v = info.getValue() as string | undefined
          return v ? new Date(v).toLocaleDateString() : '—'
        },
      }),
    ],
    [],
  )

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Trader Registration</h1>
          <p className="text-sm text-muted">Trader master profiles and commission setup.</p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onSearch()}
            placeholder="Search by name, GSTIN, PAN, mobile…"
            className="w-64"
          />
          <Button variant="outline" onClick={onSearch}>
            Search
          </Button>
          <Permission permission="traders:write">
            <Button onClick={() => setFormOpen(true)}>
              <Plus className="mr-1 h-4 w-4" />
              New Trader
            </Button>
          </Permission>
        </div>
      </div>

      <SmartTable<Trader>
        columns={columns}
        data={traders.data?.items ?? []}
        loading={traders.isLoading}
        searchPlaceholder="Filter list…"
        exportName="traders"
        filterKey="traders-list"
        onRowClick={(row) => navigate(`/traders/${row.id}`)}
      />

      <TraderForm
        open={formOpen}
        onOpenChange={setFormOpen}
        onSaved={() => queryClient.invalidateQueries({ queryKey: ['traders'] })}
      />
    </div>
  )
}
