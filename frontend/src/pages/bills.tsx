import { useQuery } from '@tanstack/react-query'
import { createColumnHelper, type ColumnDef } from '@tanstack/react-table'
import { FileText, IndianRupee, Printer, Scale } from 'lucide-react'
import { useMemo, useState } from 'react'

import { SmartTable } from '@/components/data/smart-table'
import { StatCard } from '@/components/data/stat-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { api } from '@/lib/api'
import type { ListResponse } from '@/lib/types'

export interface BillOut {
  id: number
  trader_name: string
  trader_id?: string | null
  bill_number: string
  commodity: string
  date?: string | null
  vehicle_number?: string | null
  weight: number
  rate?: number | null
  gross_amount: number
  hammali_rate: number
  hammali_amount: number
  total_amount: number
  account_holder?: string | null
  bank_name?: string | null
  account_number?: string | null
  ifsc_code?: string | null
  payment_alert_triggered?: boolean
  printed?: boolean
  printed_at?: string | null
  printed_by?: string | null
  raw_data?: unknown
  created_at?: string | null
}

const columnHelper = createColumnHelper<BillOut>()

function fmt(value: number | null | undefined, prefix = ''): string {
  if (value === null || value === undefined) return '—'
  return `${prefix}${value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

export function BillsPage() {
  const [printedFilter, setPrintedFilter] = useState('')

  const bills = useQuery({
    queryKey: ['bills-list', printedFilter],
    queryFn: () => {
      const qs = printedFilter ? `?printed=${printedFilter === 'printed'}` : '?limit=200'
      return api<ListResponse<BillOut>>(`/api/bills${qs}`)
    },
    refetchInterval: 30_000,
  })

  const items = bills.data?.items ?? []

  const printedCount = items.filter((b) => b.printed).length
  const totalAmount = items.reduce((s, b) => s + (b.total_amount ?? 0), 0)
  const totalWeight = items.reduce((s, b) => s + (b.weight ?? 0), 0)
  const pendingCount = items.length - printedCount

  const columns = useMemo<ColumnDef<BillOut, any>[]>(
    () => [
      columnHelper.accessor('bill_number', {
        header: 'Bill no.',
        cell: (info) => (
          <span className="font-mono text-xs">
            {info.getValue() || <span className="text-muted">#{info.row.original.id}</span>}
          </span>
        ),
      }),
      columnHelper.accessor('trader_name', { header: 'Trader' }),
      columnHelper.accessor('commodity', {
        header: 'Commodity',
        cell: (info) => info.getValue() || <span className="text-muted">—</span>,
      }),
      columnHelper.accessor('date', {
        header: 'Date',
        cell: (info) => {
          const v = info.getValue() as string | null | undefined
          return v ? new Date(v).toLocaleDateString('en-IN') : <span className="text-muted">—</span>
        },
      }),
      columnHelper.accessor('weight', {
        header: 'Weight (kg)',
        cell: (info) => fmt(info.getValue()),
      }),
      columnHelper.accessor('rate', {
        header: 'Rate (₹/qtl)',
        cell: (info) => fmt(info.getValue(), '₹'),
      }),
      columnHelper.accessor('gross_amount', {
        header: 'Gross (₹)',
        cell: (info) => fmt(info.getValue(), '₹'),
      }),
      columnHelper.accessor('total_amount', {
        header: 'Total (₹)',
        cell: (info) => <span className="font-semibold">{fmt(info.getValue(), '₹')}</span>,
      }),
      columnHelper.accessor('printed', {
        header: 'Print',
        cell: (info) => {
          const printed = info.getValue() as boolean
          return printed ? (
            <Badge variant="success">
              <Printer className="h-3 w-3" /> Printed
            </Badge>
          ) : (
            <Badge variant="muted">Pending</Badge>
          )
        },
      }),
      columnHelper.accessor('printed_at', {
        header: 'Printed at',
        cell: (info) => {
          const v = info.getValue() as string | null | undefined
          return v ? new Date(v).toLocaleString() : <span className="text-muted">—</span>
        },
      }),
    ],
    [],
  )

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Bills</h1>
          <p className="text-sm text-muted">e-Mandi bill records and print history.</p>
        </div>
        <Card>
          <CardContent className="flex items-center gap-2 p-2">
            <Select
              aria-label="Print status filter"
              value={printedFilter}
              onChange={(e) => setPrintedFilter(e.target.value)}
              options={[
                { value: '', label: 'All bills' },
                { value: 'printed', label: 'Printed' },
                { value: 'pending', label: 'Pending' },
              ]}
              className="w-40"
            />
            <Button variant="outline" onClick={() => bills.refetch()} disabled={bills.isFetching}>
              Refresh
            </Button>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total bills"
          icon={<FileText className="h-4 w-4" />}
          value={fmt(items.length)}
          hint={bills.data?.total != null ? `${bills.data.total} on server` : undefined}
          loading={bills.isLoading}
        />
        <StatCard
          label="Total value"
          icon={<IndianRupee className="h-4 w-4" />}
          value={fmt(totalAmount, '₹')}
          hint="sum of total amount"
          loading={bills.isLoading}
        />
        <StatCard
          label="Total weight"
          icon={<Scale className="h-4 w-4" />}
          value={`${fmt(totalWeight)} kg`}
          hint="from loaded bills"
          loading={bills.isLoading}
        />
        <StatCard
          label="Printed / pending"
          icon={<Printer className="h-4 w-4" />}
          value={`${printedCount} / ${pendingCount}`}
          hint="print status"
          loading={bills.isLoading}
        />
      </div>

      <SmartTable<BillOut>
        columns={columns}
        data={items}
        loading={bills.isLoading}
        searchPlaceholder="Search trader, commodity, bill no…"
        exportName="bills"
        filterKey="bills-list"
      />
    </div>
  )
}
