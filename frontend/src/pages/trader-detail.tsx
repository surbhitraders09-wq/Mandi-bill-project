import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, FileText, Landmark, Phone, Store, Users } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { useState } from 'react'

import { TraderForm } from '@/components/forms/trader-form'
import { Permission } from '@/components/layout/permission'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import type { Trader } from '@/lib/types'
import { toast } from '@/lib/toast'
import { cn } from '@/lib/utils'

const TABS = ['Overview', 'Stock', 'Bills', 'Payments', 'Documents'] as const
type Tab = (typeof TABS)[number]

export function TraderDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<Tab>('Overview')
  const [editOpen, setEditOpen] = useState(false)

  const trader = useQuery({
    queryKey: ['trader', id],
    queryFn: () => api<Trader>(`/api/v1/traders/${id}`),
    enabled: Boolean(id),
  })

  const traderData = trader.data

  const deleteTrader = async () => {
    if (!traderData) return
    if (!window.confirm(`Delete trader ${traderData.name}? This cannot be undone.`)) return
    try {
      await api(`/api/v1/traders/${traderData.id}`, { method: 'DELETE' })
      toast.success('Trader deleted')
      queryClient.invalidateQueries({ queryKey: ['traders'] })
      navigate('/traders')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="icon" onClick={() => navigate('/traders')} aria-label="Back to traders">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold">Trader Profile</h1>
            <p className="text-sm text-muted">Master record, licenses and activity.</p>
          </div>
        </div>
        <Permission permission="traders:write">
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setEditOpen(true)}>
              Edit
            </Button>
            <Button variant="danger" onClick={deleteTrader}>
              Delete
            </Button>
          </div>
        </Permission>
      </div>

      {trader.isLoading || !traderData ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-64 lg:col-span-1" />
          <Skeleton className="h-64 lg:col-span-2" />
        </div>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Store className="h-4 w-4 text-muted" />
                  {traderData.name}
                </CardTitle>
                <CardDescription>Trader ID #{traderData.id}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted">Mobile</span>
                  <span>{traderData.mobile ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Commission</span>
                  <span>{traderData.commission_rate}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Registered</span>
                  <span>{traderData.created_at ? new Date(traderData.created_at).toLocaleDateString() : '—'}</span>
                </div>
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-base">Licenses & tax identifiers</CardTitle>
                <CardDescription>Trade license and tax registrations on file.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-muted">
                    <Landmark className="h-4 w-4" />
                    GSTIN
                  </span>
                  <span className="font-mono">{traderData.gstin ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-muted">
                    <FileText className="h-4 w-4" />
                    PAN
                  </span>
                  <span className="font-mono">{traderData.pan ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-muted">
                    <Phone className="h-4 w-4" />
                    License no.
                  </span>
                  <span className="font-mono">{traderData.license_no ?? '—'}</span>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="flex gap-1 border-b border-border">
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={cn(
                  'rounded-t-md px-3 py-2 text-sm font-medium transition-colors',
                  tab === t ? 'border-b-2 border-primary text-text' : 'text-muted hover:text-text',
                )}
              >
                {t}
              </button>
            ))}
          </div>

          {tab === 'Overview' && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <EmptyState
                  title="No stock or billing activity yet"
                  description="Trader stock balances and bills will appear here from Phase 2 onward."
                />
              </CardContent>
            </Card>
          )}
          {tab !== 'Overview' && (
            <Card>
              <CardContent>
                <EmptyState
                  icon={<Users className="h-8 w-8" />}
                  title={`${tab} will land here`}
                  description={`The ${tab.toLowerCase()} ledger for this trader is part of Phase 2 (stock & bills).`}
                />
              </CardContent>
            </Card>
          )}
        </>
      )}

      <TraderForm
        open={editOpen}
        onOpenChange={setEditOpen}
        trader={traderData}
        onSaved={() => queryClient.invalidateQueries({ queryKey: ['trader', id] })}
      />
    </div>
  )
}
