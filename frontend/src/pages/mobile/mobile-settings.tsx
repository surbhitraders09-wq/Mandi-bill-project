import { useNavigate } from 'react-router-dom'
import { useState, type FormEvent } from 'react'

import { MobileHeader, MobileLayout } from '@/components/mobile/mobile-layout'
import { adminLogin, fetchSettings, updateSetting, type MobileSetting } from '@/lib/mobile'
import { toast } from '@/lib/toast'

export function MobileSettingsPage() {
  const navigate = useNavigate()
  const [token, setToken] = useState<string | null>(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [unlocking, setUnlocking] = useState(false)

  const [items, setItems] = useState<Record<string, MobileSetting>>({})
  const [values, setValues] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [savingKey, setSavingKey] = useState<string | null>(null)

  async function handleUnlock(e: FormEvent) {
    e.preventDefault()
    if (!username.trim() || !password) {
      toast.error('यूज़रनेम और पासवर्ड दर्ज करें')
      return
    }
    setUnlocking(true)
    try {
      const res = await adminLogin(username.trim(), password)
      setToken(res.access_token)
      setLoading(true)
      try {
        const data = await fetchSettings(res.access_token)
        const map = data.items ?? {}
        setItems(map)
        setValues(Object.fromEntries(Object.entries(map).map(([k, v]) => [k, v.value ?? ''])))
      } finally {
        setLoading(false)
      }
      toast.success('अनलॉक हो गया', 'सेटिंग्स बदल सकते हैं')
    } catch (err) {
      toast.error('अनलॉक नहीं हुआ', err instanceof Error ? err.message : undefined)
    } finally {
      setUnlocking(false)
    }
  }

  async function handleSave(key: string) {
    if (savingKey) return
    setSavingKey(key)
    try {
      await updateSetting(token!, key, values[key] ?? '')
      toast.success('सेव हो गया')
    } catch (err) {
      toast.error('सेव नहीं हुआ', err instanceof Error ? err.message : undefined)
    } finally {
      setSavingKey(null)
    }
  }

  const toggleChange = (key: string, checked: boolean) => {
    setValues((v) => ({ ...v, [key]: String(checked) }))
    void handleSave(key)
  }

  return (
    <MobileLayout>
      <MobileHeader title="सेटिंग्स" onBack={() => navigate('/mobile')} hideSettings />

      {!token ? (
        <form onSubmit={handleUnlock} className="flex flex-col gap-3">
          <p className="text-sm text-muted">
            पासवर्ड, पिन या यूज़र ID बदलने के लिए एडमिन पासवर्ड से अनलॉक करें।
          </p>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">यूज़रनेम</span>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoCapitalize="none"
              className="rounded-md border border-border bg-bg px-3 py-2.5 text-sm outline-none focus:border-primary"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">पासवर्ड</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-md border border-border bg-bg px-3 py-2.5 text-sm outline-none focus:border-primary"
            />
          </label>
          <button
            type="submit"
            disabled={unlocking}
            className="mt-2 rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          >
            {unlocking ? 'अनलॉक हो रहा है…' : 'अनलॉक करें'}
          </button>
        </form>
      ) : loading ? (
        <p className="py-10 text-center text-sm text-muted">सेटिंग्स लोड हो रही हैं…</p>
      ) : (
        <div className="flex flex-col gap-4">
          {Object.values(items).map((s) => (
            <div key={s.key} className="rounded-md border border-border bg-surface p-3">
              <p className="text-sm font-semibold text-text">{s.display_name ?? s.key}</p>
              {s.description && <p className="mt-0.5 text-xs text-muted">{s.description}</p>}
              {s.type === 'toggle' ? (
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-sm text-muted">{values[s.key] === 'true' || values[s.key] === '1' ? 'चालू' : 'बंद'}</span>
                  <input
                    type="checkbox"
                    checked={values[s.key] === 'true' || values[s.key] === '1'}
                    onChange={(e) => toggleChange(s.key, e.target.checked)}
                    className="h-5 w-5 accent-[var(--color-primary)]"
                  />
                </div>
              ) : (
                <div className="mt-2 flex items-end gap-2">
                  <input
                    type={s.type === 'password' || s.encrypted ? 'password' : 'text'}
                    value={values[s.key] ?? ''}
                    onChange={(e) => setValues((v) => ({ ...v, [s.key]: e.target.value }))}
                    className="min-w-0 flex-1 rounded-md border border-border bg-bg px-3 py-2 text-sm outline-none focus:border-primary"
                  />
                  <button
                    type="button"
                    onClick={() => handleSave(s.key)}
                    disabled={savingKey === s.key}
                    className="rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
                  >
                    {savingKey === s.key ? 'सेव…' : 'सेव'}
                  </button>
                </div>
              )}
            </div>
          ))}
          <button
            type="button"
            onClick={() => {
              setToken(null)
              setItems({})
              setValues({})
              setPassword('')
            }}
            className="mt-1 rounded-lg border border-border px-4 py-3 text-sm font-semibold text-muted"
          >
            लॉक करें
          </button>
        </div>
      )}
    </MobileLayout>
  )
}
