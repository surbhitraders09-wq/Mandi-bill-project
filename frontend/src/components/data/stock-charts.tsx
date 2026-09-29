import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { StockAnalytics } from '@/lib/types'

const SEGMENT_COLORS: Record<string, string> = {
  trader: 'var(--color-primary)',
  government: '#f97316',
}
const COMMODITY_COLORS = ['var(--color-primary)', '#f97316', '#10b981', '#8b5cf6', '#ef4444', '#f59e0b', '#06b6d4', '#84cc16']

interface StockChartsProps {
  analytics?: StockAnalytics
  loading?: boolean
}

export function StockCharts({ analytics, loading = false }: StockChartsProps) {
  if (loading) {
    return (
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-3"><CardContent className="pt-6"><Skeleton className="h-64 w-full" /></CardContent></Card>
        <Card className="lg:col-span-2"><CardContent className="pt-6"><Skeleton className="h-64 w-full" /></CardContent></Card>
        <Card><CardContent className="pt-6"><Skeleton className="h-64 w-full" /></CardContent></Card>
      </div>
    )
  }
  if (!analytics) return null

  const byValue = analytics.by_commodity.map((c) => ({ ...c }))
  const bySegment = analytics.by_segment.map((s) => ({ ...s, label: s.name === 'government' ? 'Government' : 'Trader' }))

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-3">
        <CardHeader>
          <CardTitle className="text-base">Daily purchase trend</CardTitle>
        </CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={analytics.daily} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="valueGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-primary)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--color-primary)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="date" stroke="var(--color-muted)" fontSize={11} />
              <YAxis stroke="var(--color-muted)" fontSize={11} />
              <Tooltip formatter={(v) => `₹${Number(v ?? 0).toLocaleString('en-IN')}`} />
              <Area type="monotone" dataKey="value" name="Value (₹)" stroke="var(--color-primary)" fill="url(#valueGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="text-base">Commodity value split</CardTitle>
        </CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={byValue}
                dataKey="value"
                nameKey="name"
                innerRadius={40}
                outerRadius={80}
                paddingAngle={2}
                label={(p) => p.name}
              >
                {byValue.map((c, i) => (
                  <Cell key={c.name} fill={COMMODITY_COLORS[i % COMMODITY_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => `₹${Number(v ?? 0).toLocaleString('en-IN')}`} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Segment split (bills)</CardTitle>
        </CardHeader>
        <CardContent className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bySegment} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
              <XAxis dataKey="label" stroke="var(--color-muted)" fontSize={11} />
              <YAxis stroke="var(--color-muted)" fontSize={11} />
              <Tooltip />
              <Bar dataKey="bills" name="Bills" radius={[4, 4, 0, 0]}>
                {bySegment.map((s) => (
                  <Cell key={s.name} fill={SEGMENT_COLORS[s.name] ?? 'var(--color-primary)'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  )
}
