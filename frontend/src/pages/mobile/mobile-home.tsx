import { useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'

import { MobileLayout } from '@/components/mobile/mobile-layout'
import { searchTodayBills } from '@/lib/mobile'
import { toast } from '@/lib/toast'
import { useMobileBills } from '@/stores/mobile-bills'

const SEARCH_STEPS = [
  'सर्वर से जुड़ रहा है…',
  'e-Mandi पोर्टल में लॉगिन हो रहा है…',
  'कैप्चा हल किया जा रहा है…',
  'आज के अनुबंध खोजे जा रहे हैं…',
]

interface ApiState {
  state: string
  busy: boolean
  found_bills: number
  progress?: string
  show_captcha?: boolean
}

export function MobileHomePage() {
  const navigate = useNavigate()
  const setResults = useMobileBills((s) => s.setResults)
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
          // A fresh captcha after a submit means the previous answer was wrong —
          // let the user retry. The same image means the backend is still
          // verifying the submitted answer.
          if (captchaSubmittedRef.current && image && image !== captchaImageRef.current) {
            setCaptchaSubmitted(false)
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
      const res = await searchTodayBills()
      if (pollRef.current) clearInterval(pollRef.current)
      if (!res.bills.length) {
        toast.info('कोई बिल नहीं', 'आज की तारीख के लिए कोई अनुबंध पत्रक नहीं मिला।')
        return
      }
      setResults(res.bills, res.date)
      setServerProgress('')
      navigate('/mobile/bills', { replace: true })
    } catch (err) {
      if (pollRef.current) clearInterval(pollRef.current)
      const msg = err instanceof Error ? err.message : 'कुछ गलत हो गया'
      setError(msg)
      toast.error('खोज विफल', msg)
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
      <div className="flex min-h-[70vh] flex-col items-center justify-center text-center">
        <button
          type="button"
          onClick={() => navigate('/mobile/settings')}
          className="absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-md text-muted transition-colors hover:bg-border/60 active:bg-border"
          aria-label="सेटिंग्स"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
        <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <path d="M14 2v6h6" />
            <path d="M9 16l2 2 4-4" />
          </svg>
        </div>
        <h1 className="text-2xl font-bold">आज के बिल</h1>
        <p className="mt-2 max-w-xs text-sm leading-relaxed text-muted">
          e-Mandi पोर्टल से आज के अनुबंध पत्रक खोजें, राशि की गणना करें और लैपटॉप पर छापें।
        </p>

        {error && (
          <div className="mt-6 w-full rounded-md border border-danger/30 bg-danger/5 p-3 text-left text-sm text-danger">
            {error}
          </div>
        )}

        {showCaptcha && captchaImage && (
          <div className="mt-6 w-full rounded-md border border-border bg-surface p-4 text-left shadow-card">
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

        <div className="mt-8 w-full">
          {loading ? (
            <div className="flex flex-col items-center gap-3">
              <div className="h-10 w-10 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
              <p className="text-sm text-muted">{serverProgress || SEARCH_STEPS[step]}</p>
            </div>
          ) : (
            <button
              type="button"
              onClick={handleSearch}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-6 py-4 text-base font-semibold text-primary-foreground shadow-card transition-transform active:scale-[0.98]"
            >
              आज के बिल खोजें
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m9 18 6-6-6-6" />
              </svg>
            </button>
          )}
        </div>

        <p className="mt-6 text-xs text-muted">
          खोज पूरी होने पर सभी बिल एक साथ दिखेंगे। चयनित बिल का प्रिंट लैपटॉप से निकलेगा।
        </p>
      </div>
    </MobileLayout>
  )
}
