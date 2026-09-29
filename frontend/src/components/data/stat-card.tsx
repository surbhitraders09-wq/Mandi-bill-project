import type { ReactNode } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

interface StatCardProps {
  label: string
  icon?: ReactNode
  value?: ReactNode
  hint?: string
  loading?: boolean
}

export function StatCard({ label, icon, value, hint, loading = false }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted">{label}</CardTitle>
        {icon && <span className="text-muted">{icon}</span>}
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <p className="text-2xl font-semibold tabular-nums">{value}</p>
        )}
        {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
      </CardContent>
    </Card>
  )
}
