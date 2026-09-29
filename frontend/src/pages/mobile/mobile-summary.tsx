import { Component, type ErrorInfo, type ReactNode, useEffect, useRef, useState } from 'react'

import { MobileHeader, MobileLayout } from '@/components/mobile/mobile-layout'
import { searchSummary } from '@/lib/mobile'
import type { SummaryResponse } from '@/lib/mobile'
import { toast } from '@/lib/toast'
import { useMobileBills } from '@/stores/mobile-bills'
import { cn } from '@/lib/utils'

class ChartErrorBoundary extends Component<{ children: ReactNode; fallback?: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }
  static getDerivedStateFromError() { return { hasError: true } }
  componentDidCatch(err: Error, info: ErrorInfo) { console.error('[ChartErrorBoundary]', err, info) }
  render() {
    return this.state.hasError
      ? (this.props.fallback ?? <p className="text-sm text-muted">चार्ट लोड नहीं हो पाया।</p>)
      : this.props.children
  }
}

const SEARCH_STEPS = [
  'सर्वर से जुड़ रहा है…',
  'e-Mandi पोर्टल में लॉगिन हो रहा है…',
  'कैप्चा हल किया जा रहा है…',
  'फसल अनुसार भुगतान-पत्रक समरी रिपोर्ट लोड हो रही है…',
  'होम डैशबोर्ड व मंडी खाता पढ़ा जा रहा है…',
]

interface ApiState {
  state: string
  busy: boolean
  found_bills: number
  show_captcha: boolean
  progress?: string
}

function toDdMmYyyy(d: Date): string {
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  return `${dd}-${mm}-${d.getFullYear()}`
}

function formatMoney(n: number): string {
  return `₹ ${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function formatWeight(n: number): string {
  return `${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })} क्विं.`
}

export function MobileSummaryPage() {
  const summary = useMobileBills((s) => s.summary)
  const setSummary = useMobileBills((s) => s.setSummary)
  const [fromDate, setFromDate] = useState(() => toDdMmYyyy(new Date()))
  const [toDate, setToDate] = useState(() => toDdMmYyyy(new Date()))
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(0)
  const [serverProgress, setServerProgress] = useState('')
  const [error, setError] = useState<string | null>(null)
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
      const data = (await res.json()) as { image?: string }
      const image = data.image ?? null
      setCaptchaImage(image)
      return image
    } catch {
      setCaptchaImage(null)
      return null
    }
  }

  async function handleSearch() {
    if (!/^\d{2}-\d{2}-\d{4}$/.test(fromDate) || !/^\d{2}-\d{2}-\d{4}$/.test(toDate)) {
      toast.error('तारीख गलत है', 'तारीख dd-mm-yyyy के प्रारूप में डालें')
      return
    }
    setLoading(true)
    setError(null)
    setShowCaptcha(false)
    setCaptchaSubmitted(false)
    captchaSubmittedRef.current = false
    setCaptchaImage(null)
    captchaImageRef.current = null
    setStep(0)
    setServerProgress('')
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, SEARCH_STEPS.length - 1)), 4000)
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
          // Login succeeded (or the run ended): close the dialog only then.
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
      const res = await searchSummary(fromDate, toDate)
      if (pollRef.current) clearInterval(pollRef.current)
      setSummary(res)
      toast.success('सारांश तैयार है', `${res.found_bills} भुगतान-पत्रक मिले`)
    } catch (err) {
      if (pollRef.current) clearInterval(pollRef.current)
      const msg = err instanceof Error ? err.message : 'कुछ गलत हो गया'
      setError(msg)
      toast.error('सारांश विफल', msg)
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
        const data = (await res.json().catch(() => ({}))) as { error?: { message?: string } }
        toast.error('कैप्चा जमा नहीं हुआ', data.error?.message)
        return
      }
      // Keep the dialog open; it closes only once the backend confirms the
      // login actually succeeded (poll sees state leave awaiting_captcha).
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
      <MobileHeader title="सारांश" />

      <div className="rounded-md border border-border bg-surface p-4 shadow-card">
        <label className="text-xs font-medium text-muted">दिनांक (से)</label>
        <input
          type="text"
          inputMode="numeric"
          value={fromDate}
          onChange={(e) => setFromDate(e.target.value)}
          placeholder="dd-mm-yyyy"
          className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2.5 text-sm font-mono outline-none focus:border-primary"
        />
        <label className="mt-3 block text-xs font-medium text-muted">दिनांक (तक)</label>
        <input
          type="text"
          inputMode="numeric"
          value={toDate}
          onChange={(e) => setToDate(e.target.value)}
          placeholder="dd-mm-yyyy"
          className="mt-1 w-full rounded-md border border-border bg-bg px-3 py-2.5 text-sm font-mono outline-none focus:border-primary"
        />
        <button
          type="button"
          onClick={handleSearch}
          disabled={loading}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-6 py-3.5 text-base font-semibold text-primary-foreground shadow-card transition-transform active:scale-[0.98] disabled:opacity-60"
        >
          {loading ? (serverProgress || SEARCH_STEPS[step]) : 'सारांश देखें'}
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

      <ChartErrorBoundary fallback={<p className="mt-4 text-sm text-danger">सारांश दिखाने में त्रुटि हुई। कृपया दोबारा प्रयास करें।</p>}>
        {summary && <SummaryView summary={summary} />}
      </ChartErrorBoundary>
    </MobileLayout>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-5">
      <h2 className="mb-2 text-sm font-semibold text-text">{title}</h2>
      {children}
    </div>
  )
}

function SummaryView({ summary }: { summary: SummaryResponse }) {
  const hasStock = summary.tax_paid_stock.length > 0
  const hasMandiFee = !!summary.mandi_fee_summary

  return (
    <div className="mt-5">
      {summary.date_range.from && summary.date_range.to && (
        <p className="text-xs text-muted">
          अवधि: {summary.date_range.from} → {summary.date_range.to} · {summary.found_bills} भुगतान-पत्रक
        </p>
      )}

      <Section title="फसल अनुसार भुगतान-पत्रक समरी रिपोर्ट">
        <SummaryTable
          headers={['फसल', 'कुल वजन', 'कुल मूल्य', 'औसत दर']}
          rows={summary.crops.map((c) => [
            c.commodity,
            formatWeight(c.total_weight),
            formatMoney(c.total_amount),
            `₹ ${c.avg_rate.toLocaleString('en-IN')}/क्विं.`,
          ])}
          highlightRows={summary.soyabean ? new Set([summary.crops.indexOf(summary.soyabean)]) : new Set()}
          empty="इस अवधि में कोई भुगतान-पत्रक नहीं मिला।"
        />
      </Section>

      {summary.soyabean && (
        <div className="mt-3 rounded-md border border-primary/40 bg-primary/5 p-3">
          <p className="text-xs font-semibold text-primary">सोयाबीन औसत</p>
          <p className="mt-1 text-sm text-text">
            कुल वजन {formatWeight(summary.soyabean.total_weight)} · कुल राशि{' '}
            {formatMoney(summary.soyabean.total_amount)} · औसत दर{' '}
            <span className="font-bold text-primary">
              ₹ {summary.soyabean.avg_rate.toLocaleString('en-IN')}/क्विं.
            </span>
          </p>
        </div>
      )}

      {hasStock && (
        <Section title="फसल स्टॉक (जिस पर मंडी शुल्क दिया गया)">
          <SummaryTable
            headers={['फसल', 'कुल वजन']}
            rows={summary.tax_paid_stock.map((s) => [s.commodity, formatWeight(s.total_weight)])}
            empty=""
          />
        </Section>
      )}

      {hasMandiFee && (
        <Section title="मंडी फीस / निराश्रित शुल्क (होम डैशबोर्ड)">
          <div className="overflow-hidden rounded-md border border-border bg-surface">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-border/30 text-left text-xs text-muted">
                  <th className="px-3 py-2 font-medium">कुल भुगतान-पत्रक</th>
                  <th className="px-3 py-2 font-medium">कुल मात्रा</th>
                  <th className="px-3 py-2 font-medium">देय मंडी फीस</th>
                  <th className="px-3 py-2 font-medium">देय निराश्रित शुल्क</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-border/60 last:border-0">
                  <td className="px-3 py-2 font-bold text-text">{Math.round(summary.mandi_fee_summary!.total_bills)}</td>
                  <td className="px-3 py-2">{formatWeight(summary.mandi_fee_summary!.total_quantity)}</td>
                  <td className="px-3 py-2 font-medium text-primary">{formatMoney(summary.mandi_fee_summary!.mandi_fee)}</td>
                  <td className="px-3 py-2">{formatMoney(summary.mandi_fee_summary!.nirashrit_fee)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Section>
      )}

      {summary.mandi_balance > 0 && (
        <div className="mt-5 rounded-md border border-border bg-surface p-3">
          <p className="text-xs text-muted">मंडी खाता उपलब्ध शेष</p>
          <p className="mt-1 text-xl font-bold text-primary">{formatMoney(summary.mandi_balance)}</p>
        </div>
      )}
    </div>
  )
}

function SummaryTable({
  headers,
  rows,
  highlightRows,
  empty,
}: {
  headers: string[]
  rows: string[][]
  highlightRows?: Set<number>
  empty: string
}) {
  if (!rows.length) {
    return empty ? <p className="text-sm text-muted">{empty}</p> : null
  }
  return (
    <div className="overflow-hidden rounded-md border border-border bg-surface">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-border/30 text-left text-xs text-muted">
            {headers.map((h) => (
              <th key={h} className="px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className={cn(
                'border-b border-border/60 last:border-0',
                highlightRows?.has(i) && 'bg-primary/10',
              )}
            >
              {row.map((cell, j) => (
                <td key={j} className={cn('px-3 py-2', j === 0 && 'font-medium text-text')}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
