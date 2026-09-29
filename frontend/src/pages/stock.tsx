import { useQuery } from '@tanstack/react-query'
import { createColumnHelper, type ColumnDef } from '@tanstack/react-table'
import { Award, IndianRupee, Scale, TrendingUp } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { SmartTable } from '@/components/data/smart-table'
import { StatCard } from '@/components/data/stat-card'
import { StockCharts } from '@/components/data/stock-charts'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { api } from '@/lib/api'
import type { Commodity, ListResponse, StockAnalytics, StockResponse, StockRow } from '@/lib/types'

const columnHelper = createColumnHelper<StockRow>()

const SEGMENT_OPTIONS = [
  { value: '', label: 'All segments' },
  { value: 'trader', label: 'Trader' },
  { value: 'government', label: 'Government' },
]

function fmt(value: number | null | undefined, prefix = ''): string {
  if (value === null || value === undefined) return '—'
  return `${prefix}${value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function segmentLabel(segment: string): string {
  if (segment === 'government') return 'Government'
  if (segment === 'trader') return 'Trader'
  return segment.charAt(0).toUpperCase() + segment.slice(1)
}

interface StockPageProps {
  defaultSegment?: string
  title?: string
}

export function StockPage({ defaultSegment = '', title = 'Stock' }: StockPageProps) {
  const [searchParams] = useSearchParams()
  const urlCommodity = searchParams.get('commodity')

  const [commodityId, setCommodityId] = useState(urlCommodity ?? '')
  const [segment, setSegment] = useState(defaultSegment)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [applied, setApplied] = useState({
    commodityId: urlCommodity ?? '',
    segment: defaultSegment,
    from: '',
    to: '',
  })

  useEffect(() => {
    if (urlCommodity && urlCommodity !== applied.commodityId) {
      setCommodityId(urlCommodity)
      setApplied((prev) => ({ ...prev, commodityId: urlCommodity ?? '' }))
    }
  }, [urlCommodity, applied.commodityId])

  const commodities = useQuery({
    queryKey: ['commodities'],
    queryFn: () => api<ListResponse<Commodity>>('/api/v1/commodities?limit=500'),
  })

  const params = new URLSearchParams()
  if (applied.commodityId) params.set('commodity_id', applied.commodityId)
  if (applied.segment) params.set('segment', applied.segment)
  if (applied.from) params.set('date_from', applied.from)
  if (applied.to) params.set('date_to', applied.to)
  const qs = params.toString()

  const stock = useQuery({
    queryKey: ['stock', qs],
    queryFn: () => api<StockResponse>(`/api/v1/stock${qs ? `?${qs}` : ''}`),
  })

  const analytics = useQuery({
    queryKey: ['stock-analytics'],
    queryFn: () => api<StockAnalytics>('/api/v1/stock/analytics?days=30'),
  })

  const apply = () => setApplied({ commodityId, segment, from: dateFrom, to: dateTo })

  const analyticsData = analytics.data
  const totalQty = analyticsData?.total_qty
  const totalValue = analyticsData?.total_value
  const avgRate = totalQty ? ((totalValue ?? 0) * 100) / totalQty : null

  const columns = useMemo<ColumnDef<StockRow, any>[]>(
    () => [
      columnHelper.accessor('commodity_name', { header: 'Commodity', cell: (info) => info.getValue() }),
      columnHelper.accessor('segment', {
        header: 'Segment',
        cell: (info) => (
          <Badge variant={info.getValue() === 'government' ? 'warning' : 'default'}>
            {segmentLabel(info.getValue())}
          </Badge>
        ),
      }),
      columnHelper.accessor('qty', { header: 'Qty (kg)', cell: (info) => fmt(info.getValue()) }),
      columnHelper.accessor('avg_rate', {
        header: 'Avg rate (₹/qtl)',
        cell: (info) => fmt(info.getValue(), '₹'),
      }),
      columnHelper.accessor('value', { header: 'Value (₹)', cell: (info) => fmt(info.getValue(), '₹') }),
      columnHelper.accessor('bill_count', { header: 'Bills', cell: (info) => info.getValue() }),
      columnHelper.accessor('last_date', {
        header: 'Last date',
        cell: (info) => {
          const v = info.getValue() as string | null | undefined
          return v ? new Date(v).toLocaleDateString('en-IN') : '—'
        },
      }),
    ],
    [],
  )

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="text-sm text-muted">Live commodity stock computed from the bill ledger.</p>
        </div>
      </div>

      <Card>
        <CardContent className="flex flex-wrap items-end gap-3 p-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="stock-commodity">Commodity</Label>
            <Select
              id="stock-commodity"
              value={commodityId}
              onChange={(e) => setCommodityId(e.target.value)}
              options={[
                { value: '', label: 'All commodities' },
                ...(commodities.data?.items ?? []).map((c) => ({ value: String(c.id), label: c.name })),
              ]}
              className="w-48"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="stock-segment">Segment</Label>
            <Select
              id="stock-segment"
              value={segment}
              onChange={(e) => setSegment(e.target.value)}
              options={SEGMENT_OPTIONS}
              className="w-40"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="stock-from">From</Label>
            <Input
              id="stock-from"
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-40"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="stock-to">To</Label>
            <Input
              id="stock-to"
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-40"
            />
          </div>
          <Button onClick={apply}>Apply</Button>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total qty"
          icon={<Scale className="h-4 w-4" />}
          value={fmt(totalQty)}
          hint="kg"
          loading={analytics.isLoading}
        />
        <StatCard
          label="Total value"
          icon={<IndianRupee className="h-4 w-4" />}
          value={fmt(totalValue, '₹')}
          hint="30-day picture"
          loading={analytics.isLoading}
        />
        <StatCard
          label="Avg rate"
          icon={<TrendingUp className="h-4 w-4" />}
          value={fmt(avgRate, '₹')}
          hint="₹/qtl"
          loading={analytics.isLoading}
        />
        <StatCard
          label="Top commodity"
          icon={<Award className="h-4 w-4" />}
          value={analyticsData?.top_commodity ?? '—'}
          hint="by value, 30 days"
          loading={analytics.isLoading}
        />
      </div>

      <StockCharts analytics={analytics.data} loading={analytics.isLoading} />

      <SmartTable<StockRow>
        columns={columns}
        data={stock.data?.rows ?? []}
        loading={stock.isLoading}
        searchPlaceholder="Filter commodities…"
        exportName={`stock-${applied.segment || 'all'}`}
        filterKey="stock-list"
      />
    </div>
  )
}
