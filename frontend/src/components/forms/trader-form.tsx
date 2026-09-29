import { type FormEvent, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'
import type { Trader } from '@/lib/types'
import { toast } from '@/lib/toast'

interface TraderFormProps {
  open: boolean
  onOpenChange: (v: boolean) => void
  trader?: Trader | null
  onSaved: () => void
}

export function TraderForm({ open, onOpenChange, trader, onSaved }: TraderFormProps) {
  const editing = Boolean(trader)
  const [name, setName] = useState(trader?.name ?? '')
  const [gstin, setGstin] = useState(trader?.gstin ?? '')
  const [pan, setPan] = useState(trader?.pan ?? '')
  const [licenseNo, setLicenseNo] = useState(trader?.license_no ?? '')
  const [mobile, setMobile] = useState(trader?.mobile ?? '')
  const [commission, setCommission] = useState(trader?.commission_rate?.toString() ?? '0')
  const [saving, setSaving] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      toast.error('Trader name is required')
      return
    }
    setSaving(true)
    try {
      const body = {
        name: name.trim(),
        gstin: gstin.trim() || null,
        pan: pan.trim().toUpperCase() || null,
        license_no: licenseNo.trim() || null,
        mobile: mobile.trim() || null,
        commission_rate: Number(commission) || 0,
      }
      if (editing && trader) {
        await api(`/api/v1/traders/${trader.id}`, { method: 'PUT', body: JSON.stringify(body) })
      } else {
        await api('/api/v1/traders', { method: 'POST', body: JSON.stringify(body) })
      }
      toast.success(editing ? 'Trader updated' : 'Trader registered')
      onSaved()
      onOpenChange(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{editing ? 'Edit Trader' : 'New Trader'}</DialogTitle>
          <DialogDescription>Register or update a trader profile.</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="t-name">Name</Label>
              <Input id="t-name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="t-mobile">Mobile</Label>
              <Input id="t-mobile" value={mobile} onChange={(e) => setMobile(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="t-gstin">GSTIN</Label>
              <Input id="t-gstin" value={gstin} onChange={(e) => setGstin(e.target.value.toUpperCase())} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="t-pan">PAN</Label>
              <Input id="t-pan" value={pan} onChange={(e) => setPan(e.target.value.toUpperCase())} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="t-license">License no.</Label>
              <Input id="t-license" value={licenseNo} onChange={(e) => setLicenseNo(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="t-commission">Commission rate (%)</Label>
              <Input
                id="t-commission"
                value={commission}
                onChange={(e) => setCommission(e.target.value)}
                inputMode="decimal"
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : editing ? 'Save changes' : 'Register trader'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
