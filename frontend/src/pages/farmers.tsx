import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createColumnHelper, type ColumnDef } from '@tanstack/react-table'
import { Plus } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { SmartTable } from '@/components/data/smart-table'
import { FarmerForm } from '@/components/forms/farmer-form'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Permission } from '@/components/layout/permission'
import { api } from '@/lib/api'
import type { Farmer, ListResponse } from '@/lib/types'

const columnHelper = createColumnHelper<Farmer>()

export function FarmersPage() {
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const farmers = useQuery({
    queryKey: ['farmers', debouncedQ],
    queryFn: () =>
      api<ListResponse<Farmer>>(`/api/v1/farmers?limit=500${debouncedQ ? `&q=${encodeURIComponent(debouncedQ)}` : ''}`),
  })

  const onSearch = () => setDebouncedQ(q.trim())

  const columns = useMemo<ColumnDef<Farmer, any>[]>(
    () => [
      columnHelper.accessor('name', { header: 'Name', cell: (info) => info.getValue() }),
      columnHelper.accessor('aadhaar', { header: 'Aadhaar', cell: (info) => info.getValue() }),
      columnHelper.accessor('mobile', { header: 'Mobile', cell: (info) => info.getValue() ?? '—' }),
      columnHelper.accessor('village_name', { header: 'Village', cell: (info) => info.getValue() ?? '—' }),
      columnHelper.accessor('bank_name', { header: 'Bank', cell: (info) => info.getValue() ?? '—' }),
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
          <h1 className="text-2xl font-semibold">Farmer Registration</h1>
          <p className="text-sm text-muted">Farmer master profiles and payment history.</p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onSearch()}
            placeholder="Search by name, Aadhaar, mobile…"
            className="w-64"
          />
          <Button variant="outline" onClick={onSearch}>
            Search
          </Button>
          <Permission permission="farmers:write">
            <Button onClick={() => setFormOpen(true)}>
              <Plus className="mr-1 h-4 w-4" />
              New Farmer
            </Button>
          </Permission>
        </div>
      </div>

      <SmartTable<Farmer>
        columns={columns}
        data={farmers.data?.items ?? []}
        loading={farmers.isLoading}
        searchPlaceholder="Filter list…"
        exportName="farmers"
        filterKey="farmers-list"
        onRowClick={(row) => navigate(`/farmers/${row.id}`)}
      />

      <FarmerForm
        open={formOpen}
        onOpenChange={setFormOpen}
        onSaved={() => queryClient.invalidateQueries({ queryKey: ['farmers'] })}
      />
    </div>
  )
}
