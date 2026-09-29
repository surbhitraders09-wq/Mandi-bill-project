import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Eye, EyeOff } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { api } from '@/lib/api'
import { toast } from '@/lib/toast'

interface SettingItem {
  key: string
  value: string
  display_name: string
  description: string
  encrypted: boolean
  type: 'text' | 'password' | 'number' | 'toggle'
}

type SettingsMap = Record<string, SettingItem>

export function SettingsPage() {
  const queryClient = useQueryClient()
  const [values, setValues] = useState<Record<string, string>>({})

  const settings = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const data = await api<{ items: SettingsMap }>('/api/settings')
      setValues(Object.fromEntries(Object.entries(data.items ?? {}).map(([k, v]) => [k, v.value ?? ''])))
      return data.items ?? {}
    },
  })

  const mutation = useMutation({
    mutationFn: async ({ key, value }: { key: string; value: string }) => {
      await api(`/api/settings/${key}`, { method: 'PUT', body: JSON.stringify({ value }) })
    },
    onSuccess: async () => {
      toast.success('Setting saved')
      await queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : 'Save failed'),
  })

  const items = settings.data ?? {}

  const save = (key: string) => mutation.mutate({ key, value: values[key] ?? '' })

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-muted">Portal credentials and automation preferences.</p>
      </div>

      {settings.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="pt-6">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="mt-3 h-9 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {Object.values(items).map((s) => (
            <Card key={s.key}>
              <CardHeader>
                <CardTitle className="text-base">{s.display_name}</CardTitle>
                <CardDescription>{s.description}</CardDescription>
              </CardHeader>
              <CardContent>
                {s.type === 'toggle' ? (
                  <div className="flex items-center justify-between">
                    <Switch
                      checked={values[s.key] === 'true' || values[s.key] === '1'}
                      onCheckedChange={(checked) => {
                        setValues((v) => ({ ...v, [s.key]: String(checked) }))
                        mutation.mutate({ key: s.key, value: String(checked) })
                      }}
                      aria-label={s.display_name}
                    />
                    <Button size="sm" variant="outline" onClick={() => save(s.key)}>
                      <Check className="mr-1 h-3.5 w-3.5" />
                      Save
                    </Button>
                  </div>
                ) : (
                  <div className="flex items-end gap-2">
                    <PasswordInput
                      item={s}
                      value={values[s.key] ?? ''}
                      onChange={(val) => setValues((v) => ({ ...v, [s.key]: val }))}
                    />
                    <Button size="sm" variant="outline" onClick={() => save(s.key)} disabled={mutation.isPending}>
                      <Check className="mr-1 h-3.5 w-3.5" />
                      Save
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

function PasswordInput({
  item,
  value,
  onChange,
}: {
  item: SettingItem
  value: string
  onChange: (v: string) => void
}) {
  const [reveal, setReveal] = useState(false)
  const showReveal = item.type === 'password' || item.encrypted
  return (
    <div className="flex flex-1 flex-col gap-1.5">
      <Label htmlFor={item.key} className="sr-only">
        {item.display_name}
      </Label>
      <div className="relative">
        <Input
          id={item.key}
          type={showReveal && !reveal ? 'password' : 'text'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="pr-9"
        />
        {showReveal && (
          <button
            type="button"
            onClick={() => setReveal((r) => !r)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-text"
            aria-label={reveal ? 'Hide value' : 'Show value'}
          >
            {reveal ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        )}
      </div>
    </div>
  )
}
