import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Banknote, Landmark, Phone, User, Users } from 'lucide-react'
import { useNavigate, useParams } from 'react-router-dom'
import { useState } from 'react'

import { FarmerForm } from '@/components/forms/farmer-form'
import { Permission } from '@/components/layout/permission'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import type { Farmer } from '@/lib/types'
import { toast } from '@/lib/toast'
import { cn } from '@/lib/utils'

const TABS = ['Overview', 'Purchases', 'Payments', 'Documents', 'Timeline'] as const
type Tab = (typeof TABS)[number]

export function FarmerDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<Tab>('Overview')
  const [editOpen, setEditOpen] = useState(false)

  const farmer = useQuery({
    queryKey: ['farmer', id],
    queryFn: () => api<Farmer>(`/api/v1/farmers/${id}`),
    enabled: Boolean(id),
  })

  const farmerData = farmer.data

  const deleteFarmer = async () => {
    if (!farmerData) return
    if (!window.confirm(`Delete farmer ${farmerData.name}? This cannot be undone.`)) return
    try {
      await api(`/api/v1/farmers/${farmerData.id}`, { method: 'DELETE' })
      toast.success('Farmer deleted')
      queryClient.invalidateQueries({ queryKey: ['farmers'] })
      navigate('/farmers')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="icon" onClick={() => navigate('/farmers')} aria-label="Back to farmers">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold">Farmer Profile</h1>
            <p className="text-sm text-muted">Master record and activity.</p>
          </div>
        </div>
        <Permission permission="farmers:write">
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setEditOpen(true)}>
              Edit
            </Button>
            <Button variant="danger" onClick={deleteFarmer}>
              Delete
            </Button>
          </div>
        </Permission>
      </div>

      {farmer.isLoading || !farmerData ? (
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
                  <User className="h-4 w-4 text-muted" />
                  {farmerData.name}
                </CardTitle>
                <CardDescription>Farmer ID #{farmerData.id}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted">Aadhaar</span>
                  <span className="font-mono">{farmerData.aadhaar}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Mobile</span>
                  <span>{farmerData.mobile ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Village</span>
                  <span>{farmerData.village_name ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Land area</span>
                  <span>{farmerData.land_area ? `${farmerData.land_area} acres` : '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Registered</span>
                  <span>{farmerData.created_at ? new Date(farmerData.created_at).toLocaleDateString() : '—'}</span>
                </div>
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-base">Bank details</CardTitle>
                <CardDescription>Payment disbursement account.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-muted">
                    <Landmark className="h-4 w-4" />
                    Bank
                  </span>
                  <span>{farmerData.bank_name ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-muted">
                    <Banknote className="h-4 w-4" />
                    Account
                  </span>
                  <span className="font-mono">{farmerData.account_number ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-muted">
                    <Phone className="h-4 w-4" />
                    IFSC
                  </span>
                  <span className="font-mono">{farmerData.ifsc_code ?? '—'}</span>
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
                  title="No purchase or payment activity yet"
                  description="Bill generation for this farmer will appear here from Phase 2 onward."
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
                  description={`The ${tab.toLowerCase()} ledger for this farmer is part of Phase 2 (bills & payments).`}
                />
              </CardContent>
            </Card>
          )}
        </>
      )}

      <FarmerForm
        open={editOpen}
        onOpenChange={setEditOpen}
        farmer={farmerData}
        onSaved={() => queryClient.invalidateQueries({ queryKey: ['farmer', id] })}
      />
    </div>
  )
}
