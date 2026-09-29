import { createColumnHelper, type ColumnDef } from '@tanstack/react-table'
import { FileSearch, Printer } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { SmartTable } from '@/components/data/smart-table'
import { StatCard } from '@/components/data/stat-card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { searchReports } from '@/lib/mobile'
import type { ApiState, ReportsResponse } from '@/lib/mobile'
import { toast } from '@/lib/toast'
import { cn } from '@/lib/utils'

const columnHelper = createColumnHelper<ReportsResponse['gatepasses'][number]>()

const STEPS = [
  'Server se jud raha hai…',
  'e-Mandi portal mein login ho raha hai…',
  'Gatepass taul ganna page khula ja raha hai…',
  'Aaj ka data load ho raha hai…',
  'Data ekatra kiya ja raha hai…',
  'Baki gatepass ki jankari dekhi ja rahi hai…',
]

export function ReportsPage() {
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(0)
  const [serverProgress, setServerProgress] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<ReportsResponse | null>(null)
  const [showCaptcha, setShowCaptcha] = useState(false)
  const [captchaImage, setCaptchaImage] = useState<string | null>(null)
  const [captchaText, setCaptchaText] = useState('')
  const [captchaSubmitted, setCaptchaSubmitted] = useState(false)
  const [submittingCaptcha, setSubmittingCaptcha] = useState(false)
  const captchaImageRef = useRef<string | null>(null)
  const captchaSubmittedRef = useRef(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  async function fetchCaptchaImage(): Promise<string | null> {
    try {
      const res = await fetch('/api/automation/captcha')
      const d = (await res.json()) as { image?: string }
      const image = d.image ?? null
      setCaptchaImage(image)
      return image
    } catch {
      setCaptchaImage(null)
      return null
    }
  }

  async function handleSearch() {
    setLoading(true)
    setError(null)
    setData(null)
    setShowCaptcha(false)
    setCaptchaSubmitted(false)
    captchaSubmittedRef.current = false
    setCaptchaImage(null)
    captchaImageRef.current = null
    setStep(0)
    setServerProgress('')
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 4000)
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch('/api/automation/state')
        const st = (await res.json()) as ApiState
        if (st.progress) setServerProgress(st.progress)
        if (st.state === 'awaiting_captcha' || st.show_captcha) {
          setShowCaptcha(true)
          const image = await fetchCaptchaImage()
          if (captchaSubmittedRef.current && image && image !== captchaImageRef.current) {
            setCaptchaSubmitted(false)
            captchaSubmittedRef.current = false
          }
          captchaImageRef.current = image
        } else {
          setShowCaptcha(false)
          setCaptchaSubmitted(false)
          captchaSubmittedRef.current = false
          captchaImageRef.current = null
        }
      } catch {
        /* ignore poll errors */
      }
    }, 2000)
    try {
      const res = await searchReports()
      if (pollRef.current) clearInterval(pollRef.current)
      setData(res)
      toast.success('Report ready', `${res.total_gatepasses} gatepasses, ${res.tol_pending_count} pending`)
    } catch (err) {
      if (pollRef.current) clearInterval(pollRef.current)
      setError(err instanceof Error ? err.message : 'Something went wrong')
      toast.error('Report failed', err instanceof Error ? err.message : undefined)
    } finally {
      clearInterval(timer)
      setLoading(false)
      setServerProgress('')
    }
  }

  async function handleCaptchaSubmit() {
    if (!captchaText.trim()) return
    setSubmittingCaptcha(true)
    try {
      const res = await fetch('/api/automation/captcha', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: captchaText.trim() }),
      })
      if (!res.ok) {
        const d = (await res.json().catch(() => ({}))) as { error?: { message?: string } }
        toast.error('CAPTCHA not accepted', d.error?.message)
        return
      }
      setCaptchaSubmitted(true)
      captchaSubmittedRef.current = true
      setCaptchaText('')
      toast.info('CAPTCHA sent', 'Portal is verifying…')
    } catch (err) {
      toast.error('CAPTCHA not accepted', err instanceof Error ? err.message : undefined)
    } finally {
      setSubmittingCaptcha(false)
    }
  }

  const columns = useMemo<ColumnDef<ReportsResponse['gatepasses'][number], any>[]>(
    () => [
      columnHelper.accessor('gatepass_id', {
        header: 'Gatepass',
        cell: (info) => <span className="font-mono text-xs">{info.getValue()}</span>,
      }),
      columnHelper.accessor('trader_name', { header: 'Trader' }),
      columnHelper.accessor('commodity', { header: 'Commodity' }),
      columnHelper.accessor('weight', { header: 'Weight' }),
      columnHelper.accessor('taul_status', {
        header: 'Taul status',
        cell: (info) => info.getValue() || <span className="text-muted">—</span>,
      }),
      columnHelper.accessor('payment_status', {
        header: 'Payment',
        cell: (info) => info.getValue() || <span className="text-muted">—</span>,
      }),
      columnHelper.accessor('mobile_no', {
        header: 'Mobile',
        cell: (info) =>
          info.getValue() ? (
            <span className="font-mono text-xs">{info.getValue()}</span>
          ) : (
            <span className="text-muted">—</span>
          ),
      }),
      columnHelper.accessor('tol_pending', {
        header: 'Taul pending',
        cell: (info) =>
          info.getValue() ? <Badge variant="danger">Pending</Badge> : <Badge variant="success">Done</Badge>,
      }),
    ],
    [],
  )

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Reports</h1>
          <p className="text-sm text-muted">Gatepass taul / payment status from the e-Mandi portal.</p>
        </div>
        <Button onClick={handleSearch} disabled={loading}>
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current/30 border-t-current" />
              {serverProgress || STEPS[step]}
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <FileSearch className="h-4 w-4" /> Run today&apos;s report
            </span>
          )}
        </Button>
      </div>

      {error && (
        <div className="rounded-md border border-danger/30 bg-danger/5 p-3 text-sm text-danger">{error}</div>
      )}

      {showCaptcha && captchaImage && (
        <Card>
          <CardContent className="flex flex-wrap items-center gap-4 p-4">
            <div className="min-w-[200px] flex-1">
              <p className="text-sm font-semibold">Solve CAPTCHA</p>
              <p className="mt-0.5 text-xs text-muted">
                {captchaSubmitted
                  ? 'Your answer is being verified…'
                  : 'Automatic detection failed. Please enter the characters shown.'}
              </p>
              <img
                src={`data:image/png;base64,${captchaImage}`}
                alt="CAPTCHA"
                className="mt-3 h-20 w-full rounded-sm border border-border bg-bg object-contain"
              />
            </div>
            {captchaSubmitted ? (
              <p className="flex items-center gap-2 text-sm text-muted">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
                Verifying…
              </p>
            ) : (
              <div className="flex min-w-[240px] gap-2">
                <input
                  type="text"
                  value={captchaText}
                  onChange={(e) => setCaptchaText(e.target.value)}
                  autoCorrect="off"
                  spellCheck={false}
                  placeholder="CAPTCHA text"
                  className="flex-1 rounded-md border border-border bg-bg px-3 py-2 text-sm font-mono outline-none focus:border-primary"
                />
                <Button
                  onClick={handleCaptchaSubmit}
                  disabled={submittingCaptcha || !captchaText.trim()}
                >
                  {submittingCaptcha ? 'Sending…' : 'Submit'}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total gatepasses"
          icon={<FileSearch className="h-4 w-4" />}
          value={data ? String(data.total_gatepasses) : '—'}
          loading={loading}
        />
        <StatCard
          label="Taul pending"
          icon={<Printer className="h-4 w-4" />}
          value={data ? String(data.tol_pending_count) : '—'}
          loading={loading}
        />
        <StatCard
          label="Report date"
          icon={<FileSearch className="h-4 w-4" />}
          value={data?.date || '—'}
          loading={loading}
        />
        <StatCard
          label="State"
          icon={<FileSearch className="h-4 w-4" />}
          value={data?.state ?? 'idle'}
          loading={loading}
        />
      </div>

      {data ? (
        <SmartTable<ReportsResponse['gatepasses'][number]>
          columns={columns}
          data={data.gatepasses ?? []}
          loading={loading}
          searchPlaceholder="Search gatepass, trader, commodity…"
          exportName="gatepass-report"
          filterKey="reports-list"
        />
      ) : (
        <div className="flex flex-col gap-3">
          {loading ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <p className="rounded-md border border-border bg-surface p-6 text-center text-sm text-muted">
              No report yet. Click “Run today&apos;s report” to fetch from the portal.
            </p>
          )}
        </div>
      )}

      {loading && (
        <p className="flex items-center gap-2 text-xs text-muted">
          <span className={cn('h-3.5 w-3.5 animate-spin rounded-full border-2 border-primary/30 border-t-primary')} />
          Live progress: {serverProgress || STEPS[step]}
        </p>
      )}
    </div>
  )
}
