import { useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { api } from '@/lib/api'
import type { Farmer, ListResponse, Village } from '@/lib/types'
import { toast } from '@/lib/toast'

interface FarmerFormProps {
  open: boolean
  onOpenChange: (v: boolean) => void
  farmer?: Farmer | null
  onSaved: () => void
}

export function FarmerForm({ open, onOpenChange, farmer, onSaved }: FarmerFormProps) {
  const editing = Boolean(farmer)
  const [name, setName] = useState(farmer?.name ?? '')
  const [aadhaar, setAadhaar] = useState(farmer?.aadhaar ?? '')
  const [mobile, setMobile] = useState(farmer?.mobile ?? '')
  const [villageId, setVillageId] = useState(farmer?.village_id?.toString() ?? '')
  const [landArea, setLandArea] = useState(farmer?.land_area?.toString() ?? '')
  const [bankName, setBankName] = useState(farmer?.bank_name ?? '')
  const [accountNumber, setAccountNumber] = useState(farmer?.account_number ?? '')
  const [ifsc, setIfsc] = useState(farmer?.ifsc_code ?? '')
  const [saving, setSaving] = useState(false)

  const villages = useQuery({
    queryKey: ['villages'],
    queryFn: () => api<ListResponse<Village>>('/api/v1/villages?limit=500'),
  })

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !/^\d{12}$/.test(aadhaar)) {
      toast.error('Name and a 12-digit Aadhaar are required')
      return
    }
    setSaving(true)
    try {
      const body = {
        name: name.trim(),
        aadhaar,
        mobile: mobile.trim() || null,
        village_id: villageId ? Number(villageId) : null,
        land_area: landArea ? Number(landArea) : null,
        bank_name: bankName.trim() || null,
        account_number: accountNumber.trim() || null,
        ifsc_code: ifsc.trim() || null,
      }
      if (editing && farmer) {
        await api(`/api/v1/farmers/${farmer.id}`, { method: 'PUT', body: JSON.stringify(body) })
      } else {
        await api('/api/v1/farmers', { method: 'POST', body: JSON.stringify(body) })
      }
      toast.success(editing ? 'Farmer updated' : 'Farmer registered')
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
          <DialogTitle>{editing ? 'Edit Farmer' : 'New Farmer'}</DialogTitle>
          <DialogDescription>Register or update a farmer profile.</DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-name">Name</Label>
              <Input id="f-name" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-aadhaar">Aadhaar (12 digits)</Label>
              <Input
                id="f-aadhaar"
                value={aadhaar}
                onChange={(e) => setAadhaar(e.target.value.replace(/\D/g, '').slice(0, 12))}
                inputMode="numeric"
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-mobile">Mobile</Label>
              <Input id="f-mobile" value={mobile} onChange={(e) => setMobile(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-village">Village</Label>
              <Select
                id="f-village"
                value={villageId}
                onChange={(e) => setVillageId(e.target.value)}
                options={[
                  { value: '', label: '— Select village —' },
                  ...(villages.data?.items ?? []).map((v) => ({ value: String(v.id), label: v.name })),
                ]}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-land">Land area (acres)</Label>
              <Input
                id="f-land"
                value={landArea}
                onChange={(e) => setLandArea(e.target.value)}
                inputMode="decimal"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-bank">Bank</Label>
              <Input id="f-bank" value={bankName} onChange={(e) => setBankName(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-acct">Account number</Label>
              <Input id="f-acct" value={accountNumber} onChange={(e) => setAccountNumber(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="f-ifsc">IFSC</Label>
              <Input id="f-ifsc" value={ifsc} onChange={(e) => setIfsc(e.target.value.toUpperCase())} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : editing ? 'Save changes' : 'Register farmer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
