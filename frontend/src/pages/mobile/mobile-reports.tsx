import { useEffect, useRef, useState } from 'react'

import { MobileHeader, MobileLayout } from '@/components/mobile/mobile-layout'
import { searchReports } from '@/lib/mobile'
import type { GatepassRow, ReportsResponse } from '@/lib/mobile'
import { toast } from '@/lib/toast'
import { cn } from '@/lib/utils'

const REPORT_STEPS = [
  'सर्वर से जुड़ रहा है…',
  'e-Mandi पोर्टल में लॉगिन हो रहा है…',
  'गेटपास तौल गणना पेज खोला जा रहा है…',
  'आज का डेटा लोड हो रहा है…',
  'डेटा एकत्र किया जा रहा है…',
  'बाकी गेटपास की जानकारी देखी जा रही है…',
]

interface ApiState {
  state: string
  busy: boolean
  found_bills: number
  show_captcha: boolean
  progress?: string
}

export function MobileReportsPage() {
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(0)
  const [serverProgress, setServerProgress] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<ReportsResponse | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
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
      const res = await fetch(`/api/automation/captcha`)
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
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, REPORT_STEPS.length - 1)), 4000)
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/automation/state`)
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
      toast.success('रिपोर्ट तैयार', `${res.total_gatepasses} गेटपास मिले, ${res.tol_pending_count} बाकी`)
    } catch (err) {
      if (pollRef.current) clearInterval(pollRef.current)
      const msg = err instanceof Error ? err.message : 'कुछ गलत हो गया'
      setError(msg)
      toast.error('रिपोर्ट विफल', msg)
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
      const res = await fetch(`/api/automation/captcha`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: captchaText.trim() }),
      })
      if (!res.ok) {
        const d = (await res.json().catch(() => ({}))) as { error?: { message?: string } }
        toast.error('कैप्चा जमा नहीं हुआ', d.error?.message)
        return
      }
      setCaptchaSubmitted(true)
      captchaSubmittedRef.current = true
      setCaptchaText('')
      toast.info('कैप्चा भेजा गया', 'पोर्टल सत्यापन कर रहा है…')
    } catch (err) {
      toast.error('कैप्चा जमा नहीं हुआ', err instanceof Error ? err.message : undefined)
    } finally {
      setSubmittingCaptcha(false)
    }
  }

  return (
    <MobileLayout>
      <MobileHeader title="रिपोर्ट" />

      <div className="rounded-md border border-border bg-surface p-4 shadow-card">
        <p className="text-xs text-muted">आज की गेटपास तौल/भुगतान स्थिति देखें</p>
        <button
          type="button"
          onClick={handleSearch}
          disabled={loading}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3.5 text-base font-semibold text-primary-foreground shadow-card transition-transform active:scale-[0.98] disabled:opacity-60"
        >
          {loading ? (serverProgress || REPORT_STEPS[step]) : 'रिपोर्ट देखें'}
        </button>
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-danger/30 bg-danger/5 p-3 text-left text-sm text-danger">
          {error}
        </div>
      )}

      {showCaptcha && captchaImage && (
        <div className="mt-4 rounded-md border border-border bg-surface p-4 text-left shadow-card">
          <p className="text-sm font-semibold text-text">कैप्चा हल करें</p>
          <p className="mt-0.5 text-xs text-muted">
            {captchaSubmitted
              ? 'आपका उत्तर सत्यापित किया जा रहा है…'
              : 'स्वचालित पहचान नहीं हो पाई। कृपया चित्र में दिखे अक्षर दर्ज करें।'}
          </p>
          <img
            src={`data:image/png;base64,${captchaImage}`}
            alt="कैप्चा"
            className="mt-3 h-20 w-full rounded-sm border border-border bg-bg object-contain"
          />
          {captchaSubmitted ? (
            <p className="mt-3 flex items-center gap-2 text-sm text-muted">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
              लॉगिन सफल होते ही यह बॉक्स बंद हो जाएगा…
            </p>
          ) : (
            <div className="mt-3 flex gap-2">
              <input
                type="text"
                value={captchaText}
                onChange={(e) => setCaptchaText(e.target.value)}
                autoCorrect="off"
                spellCheck={false}
                placeholder="कैप्चा अक्षर"
                className="flex-1 rounded-md border border-border bg-bg px-3 py-2.5 text-sm font-mono outline-none focus:border-primary"
              />
              <button
                type="button"
                onClick={handleCaptchaSubmit}
                disabled={submittingCaptcha || !captchaText.trim()}
                className="rounded-md bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground disabled:opacity-50"
              >
                {submittingCaptcha ? 'भेज रहे हैं…' : 'भेजें'}
              </button>
            </div>
          )}
        </div>
      )}

      {data && (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-md border border-border bg-surface p-3 text-center shadow-card">
              <p className="text-2xl font-bold text-primary">{data.total_gatepasses}</p>
              <p className="mt-0.5 text-xs text-muted">कुल गेटपास</p>
            </div>
            <div className="rounded-md border border-danger/30 bg-danger/5 p-3 text-center shadow-card">
              <p className="text-2xl font-bold text-danger">{data.tol_pending_count}</p>
              <p className="mt-0.5 text-xs text-muted">तौल बाकी</p>
            </div>
          </div>

          <p className="text-xs text-muted">तारीख: {data.date}</p>

          {data.gatepasses.length > 0 ? (
            <div className="space-y-2">
              {data.gatepasses.map((g) => (
                <GatepassCard
                  key={g.gatepass_id}
                  gatepass={g}
                  expanded={expandedId === g.gatepass_id}
                  onToggle={() => setExpandedId(expandedId === g.gatepass_id ? null : g.gatepass_id)}
                />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">कोई गेटपास नहीं मिला।</p>
          )}
        </div>
      )}
    </MobileLayout>
  )
}

function GatepassCard({
  gatepass,
  expanded,
  onToggle,
}: {
  gatepass: GatepassRow
  expanded: boolean
  onToggle: () => void
}) {
  const g = gatepass
  return (
    <div
      className={cn(
        'rounded-md border bg-surface p-3 shadow-card transition-all',
        g.tol_pending ? 'border-danger/40' : 'border-border',
      )}
    >
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between text-left"
      >
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'h-2.5 w-2.5 rounded-full',
              g.tol_pending ? 'bg-danger' : 'bg-emerald-500',
            )}
          />
          <div>
            <p className="text-sm font-semibold text-text">{g.gatepass_id}</p>
            <p className="text-xs text-muted">{g.commodity || '—'} · {g.trader_name || '—'}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {g.tol_pending && (
            <span className="rounded-md bg-danger/10 px-1.5 py-0.5 text-[10px] font-semibold text-danger">
              तौल बाकी
            </span>
          )}
          <span className="text-xs text-muted">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

      {expanded && (
        <div className="mt-3 space-y-2 border-t border-border pt-3">
          <InfoRow label="गेटपास आईडी" value={g.gatepass_id} />
          <InfoRow label="व्यापारी" value={g.trader_name || '—'} />
          <InfoRow label="फसल" value={g.commodity || '—'} />
          <InfoRow label="वजन" value={g.weight || '—'} />
          <InfoRow label="तौल स्थिति" value={g.taul_status || (g.tol_pending ? 'बाकी' : 'पूर्ण')} />
          <InfoRow label="भुगतान" value={g.payment_status || '—'} />
          {g.mobile_no && (
            <InfoRow label="मोबाइल" value={g.mobile_no} highlight />
          )}
          {!g.mobile_no && g.tol_pending && (
            <p className="text-xs text-muted">मोबाइल नंबर उपलब्ध नहीं है</p>
          )}
        </div>
      )}
    </div>
  )
}

function InfoRow({
  label,
  value,
  highlight,
}: {
  label: string
  value: string
  highlight?: boolean
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted">{label}</span>
      <span className={cn('font-medium', highlight ? 'text-primary' : 'text-text')}>
        {value}
      </span>
    </div>
  )
}
