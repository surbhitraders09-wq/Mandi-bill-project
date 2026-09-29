import { useNavigate, useParams } from 'react-router-dom'
import { useEffect, useMemo, useRef, useState } from 'react'

import { MobileHeader, MobileLayout } from '@/components/mobile/mobile-layout'
import { getState, printPortal } from '@/lib/mobile'
import { toast } from '@/lib/toast'
import { useMobileBills } from '@/stores/mobile-bills'
import { cn } from '@/lib/utils'

const CASH_THRESHOLD = 200000

function fmt(n: number): string {
  return n.toLocaleString('en-IN', { maximumFractionDigits: 2 })
}

export function MobileBillDetailPage() {
  const { auctionId = '' } = useParams()
  const navigate = useNavigate()
  const find = useMobileBills((s) => s.find)
  const markPrinted = useMobileBills((s) => s.markPrinted)
  const printedIds = useMobileBills((s) => s.printedIds)

  const bill = useMemo(() => find(auctionId), [find, auctionId])
  const printed = printedIds.includes(auctionId)

  const [hammaliRate, setHammaliRate] = useState<string>('12.05')
  const [hammaliAmountEdit, setHammaliAmountEdit] = useState<string>('')
  const [toulRate, setToulRate] = useState<string>('0')
  const [printing, setPrinting] = useState(false)
  const [liveProgress, setLiveProgress] = useState('')
  const [liveEvents, setLiveEvents] = useState<string[]>([])
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  useEffect(() => {
    if (!bill) return
    setHammaliRate(String(bill.hammali_rate))
    setToulRate(String(bill.toul_rate))
    setHammaliAmountEdit('')
  }, [bill, bill?.auction_id])

  if (!bill) {
    return (
      <MobileLayout>
        <MobileHeader title="बिल नहीं मिला" onBack={() => navigate('/mobile/bills')} />
        <p className="text-center text-sm text-muted">यह बिल अब उपलब्ध नहीं है।</p>
      </MobileLayout>
    )
  }

  const active = bill

  const hammaliVal = parseFloat(hammaliRate)
  const toulVal = parseFloat(toulRate)
  const calculatedHammali = isFinite(hammaliVal) && hammaliVal > 0 ? active.weight * hammaliVal : 0
  // If user edited the amount directly, use that; otherwise use calculated
  const hammaliAmount = hammaliAmountEdit !== '' ? (parseFloat(hammaliAmountEdit) || 0) : calculatedHammali
  const toulAmount = isFinite(toulVal) && toulVal > 0 ? active.weight * toulVal : 0
  const payable = active.gross_amount - hammaliAmount - toulAmount
  const overLimit = payable > CASH_THRESHOLD

  async function handlePrint() {
    setPrinting(true)
    setLiveProgress('')
    setLiveEvents([])
    pollRef.current = setInterval(async () => {
      try {
        const st = await getState()
        if (st.progress) setLiveProgress(st.progress)
        const steps = (st.progress_events ?? []).map((e) => `[${e.ts}] ${e.message}`)
        if (steps.length) setLiveEvents(steps.slice(-5))
        if (!st.busy) {
          if (pollRef.current) {
            clearInterval(pollRef.current)
            pollRef.current = null
          }
        }
      } catch {
        /* ignore poll errors */
      }
    }, 1500)
    try {
      const res = await printPortal(active.auction_id, hammaliAmount, toulVal || 0)
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      if (res.printed) {
        markPrinted(active.auction_id)
        setLiveProgress('प्रिंट पूर्ण!')
        toast.success('प्रिंट हो चुका', `${active.farmer_name || 'बिल'} का भुगतान-पत्रक प्रिंट हो गया।`)
        setTimeout(() => navigate('/mobile/bills'), 1200)
      } else {
        toast.error('प्रिंट विफल', 'सर्वर ने प्रिंट स्वीकार नहीं किया।')
      }
    } catch (err) {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      toast.error('प्रिंट विफल', err instanceof Error ? err.message : undefined)
    } finally {
      setPrinting(false)
    }
  }

  return (
    <MobileLayout>
      <MobileHeader title="बिल विवरण" onBack={() => navigate('/mobile/bills')} />

      <div className="rounded-md border border-border bg-surface p-4 shadow-card">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-base font-bold text-text">{active.farmer_name || 'अनाम कृषक'}</p>
            <p className="mt-0.5 text-xs text-muted">
              {active.village || '—'} · गेटपास {active.gatepass_id || '—'}
            </p>
          </div>
          <span className="shrink-0 rounded-sm bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary">
            {active.gatepass_date || active.auction_date}
          </span>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-y-3 border-t border-border pt-3 text-sm">
          <div>
            <dt className="text-xs text-muted">कृषि उपज</dt>
            <dd className="mt-0.5 font-medium">{active.commodity}{active.variety ? ` — ${active.variety}` : ''}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">मंडी</dt>
            <dd className="mt-0.5 font-medium">{active.mandi || '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">वास्तविक वजन</dt>
            <dd className="mt-0.5 font-medium">{active.weight.toLocaleString('en-IN')} क्विं.</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">नीलामी दर</dt>
            <dd className="mt-0.5 font-medium">₹ {active.rate.toLocaleString('en-IN')}/क्विं.</dd>
          </div>
        </dl>
      </div>

      <div className="mt-4 rounded-md border border-border bg-surface p-4 shadow-card">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-text">राशि की गणना</p>
          <p className="text-xs text-muted">कुल मूल्य</p>
        </div>
        <p className="mt-1 text-2xl font-bold text-text">₹ {fmt(active.gross_amount)}</p>

        <div className="mt-4 space-y-4 border-t border-border pt-4">
          <div>
            <label htmlFor="hammali" className="flex items-center justify-between text-sm">
              <span className="font-medium">हम्माली</span>
              <span className="text-xs text-muted">₹/क्विं.</span>
            </label>
            <div className="mt-1.5 flex items-center gap-3">
              <input
                id="hammali"
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={hammaliRate}
                onChange={(e) => setHammaliRate(e.target.value)}
                className="w-28 rounded-md border border-border bg-bg px-3 py-2 text-sm font-medium outline-none focus:border-primary"
              />
              <span className="text-sm text-muted">−</span>
              <input
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={hammaliAmountEdit !== '' ? hammaliAmountEdit : calculatedHammali}
                onChange={(e) => setHammaliAmountEdit(e.target.value)}
                className="w-32 rounded-md border border-border bg-bg px-3 py-2 text-sm font-semibold text-danger outline-none focus:border-primary"
                title="हम्माली राशि (edit करें)"
              />
            </div>
          </div>

          <div>
            <label htmlFor="toul" className="flex items-center justify-between text-sm">
              <span className="font-medium">तौल</span>
              <span className="text-xs text-muted">₹/क्विं.</span>
            </label>
            <div className="mt-1.5 flex items-center gap-3">
              <input
                id="toul"
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={toulRate}
                onChange={(e) => setToulRate(e.target.value)}
                className="w-28 rounded-md border border-border bg-bg px-3 py-2 text-sm font-medium outline-none focus:border-primary"
              />
              <span className="text-sm text-muted">−</span>
              <span className="text-sm font-semibold text-danger">₹ {fmt(toulAmount)}</span>
            </div>
          </div>
        </div>

        <div className="mt-4 border-t border-border pt-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-text">किसान को भुगतान योग्य</span>
            <span className="text-lg font-bold text-text">₹ {fmt(payable)}</span>
          </div>
        </div>
      </div>

      {overLimit && (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-danger/40 bg-danger/5 p-3 text-sm text-danger">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 shrink-0">
            <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <path d="M12 9v4" />
            <path d="M12 17h.01" />
          </svg>
          <div>
            <p className="font-semibold">बिल राशि पहुंच से बाहर</p>
            <p className="mt-0.5 text-xs leading-relaxed">
              यह राशि ₹ 2,00,000 से अधिक है, इसलिए इसका प्रिंट नहीं निकाला जा सकता। कृपया मैन्युअल व्यवस्था करें।
            </p>
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={handlePrint}
        disabled={overLimit || printing || printed}
        className={cn(
          'mt-5 flex w-full items-center justify-center gap-2 rounded-lg px-6 py-4 text-base font-semibold shadow-card transition-transform active:scale-[0.98]',
          overLimit || printed
            ? 'cursor-not-allowed bg-border text-muted'
            : 'bg-primary text-primary-foreground',
        )}
      >
        {printing ? (
          <>
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-current/30 border-t-current" />
            {liveProgress || 'प्रिंट हो रहा है…'}
          </>
        ) : printed ? (
          <>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 6 9 17l-5-5" />
            </svg>
            प्रिंट हो चुका
          </>
        ) : (
          <>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 9V2h12v7" />
              <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
              <rect x="6" y="14" width="12" height="8" />
            </svg>
            भुगतान-पत्रक छापें
          </>
        )}
      </button>

      <p className="mt-3 text-center text-xs text-muted">
        प्रिंट लैपटॉप से जुड़े प्रिंटर पर निकलेगा · पोर्टल में कोई बदलाव नहीं होगा
      </p>

      {printing && liveEvents.length > 0 && (
        <div className="mt-4 rounded-md border border-border bg-surface p-3">
          <p className="text-xs font-semibold text-text">लाइव प्रगति</p>
          <ul className="mt-2 space-y-1">
            {liveEvents.map((e, i) => (
              <li key={i} className="font-mono text-[11px] leading-snug text-muted">
                {e}
              </li>
            ))}
          </ul>
        </div>
      )}
    </MobileLayout>
  )
}
