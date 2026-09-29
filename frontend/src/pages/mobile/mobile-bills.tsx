import { Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'

import { MobileHeader, MobileLayout } from '@/components/mobile/mobile-layout'
import { searchTodayBills } from '@/lib/mobile'
import { toast } from '@/lib/toast'
import { useMobileBills } from '@/stores/mobile-bills'
import { cn } from '@/lib/utils'

export function MobileBillsPage() {
  const navigate = useNavigate()
  const bills = useMobileBills((s) => s.bills)
  const date = useMobileBills((s) => s.date)
  const printedIds = useMobileBills((s) => s.printedIds)
  const setResults = useMobileBills((s) => s.setResults)
  const [refreshing, setRefreshing] = useState(false)

  async function handleRefresh() {
    setRefreshing(true)
    try {
      const res = await searchTodayBills()
      setResults(res.bills, res.date)
      toast.success('ताज़ा किया गया', `${res.bills.length} बिल मिले`)
    } catch (err) {
      toast.error('ताज़ा करना विफल', err instanceof Error ? err.message : undefined)
    } finally {
      setRefreshing(false)
    }
  }

  const grossTotal = bills.reduce((sum, b) => sum + b.gross_amount, 0)
  const payableTotal = bills.reduce((sum, b) => sum + b.payable, 0)
  const pending = bills.filter((b) => !printedIds.includes(b.auction_id))
  const printedBills = bills.filter((b) => printedIds.includes(b.auction_id))

  return (
    <MobileLayout>
      <MobileHeader title={`आज के बिल${date ? ` — ${date}` : ''}`} onBack={() => navigate('/mobile')} />

      <div className="mb-4 grid grid-cols-2 gap-3">
        <div className="rounded-md border border-border bg-surface p-3">
          <p className="text-xs text-muted">कुल मूल्य</p>
          <p className="mt-1 text-lg font-bold text-text">₹ {grossTotal.toLocaleString('en-IN')}</p>
        </div>
        <div className="rounded-md border border-border bg-surface p-3">
          <p className="text-xs text-muted">भुगतान योग्य</p>
          <p className="mt-1 text-lg font-bold text-success">₹ {payableTotal.toLocaleString('en-IN')}</p>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex flex-1 items-center justify-center gap-2 rounded-md border border-border bg-surface px-3 py-2.5 text-sm font-medium transition-colors active:bg-border/40 disabled:opacity-50"
        >
          {refreshing ? 'ताज़ा हो रहा है…' : 'ताज़ा करें'}
        </button>
        <Link
          to="/mobile"
          className="flex flex-1 items-center justify-center rounded-md border border-border bg-surface px-3 py-2.5 text-sm font-medium transition-colors active:bg-border/40"
        >
          नया खोज
        </Link>
      </div>

      <ul className="mt-4 space-y-3">
        {pending.map((bill) => {
          const overLimit = bill.payable > 200000
          return (
            <li key={bill.auction_id}>
              <Link
                to={`/mobile/bills/${encodeURIComponent(bill.auction_id)}`}
                className={cn(
                  'block rounded-md border bg-surface p-4 shadow-card transition-transform active:scale-[0.99]',
                  overLimit ? 'border-danger/40' : 'border-border',
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-text">
                      {bill.farmer_name || 'अनाम कृषक'}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-muted">
                      {bill.commodity}
                      {bill.variety ? ` — ${bill.variety}` : ''}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-sm font-bold text-text">
                      ₹ {bill.payable.toLocaleString('en-IN')}
                    </p>
                    {overLimit && (
                      <span className="mt-1 inline-block rounded-sm bg-danger/10 px-1.5 py-0.5 text-[10px] font-medium text-danger">
                        सीमा से ऊपर
                      </span>
                    )}
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between border-t border-border pt-2.5 text-xs text-muted">
                  <span>
                    वजन {bill.weight.toLocaleString('en-IN')} क्विं. · दर ₹{bill.rate.toLocaleString('en-IN')}
                  </span>
                  <span className="text-muted">विवरण →</span>
                </div>
              </Link>
            </li>
          )
        })}
      </ul>

      {printedBills.length > 0 && (
        <div className="mt-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-success">
            प्रिंट हो चुके ({printedBills.length})
          </p>
          <ul className="mt-2 space-y-2">
            {printedBills.map((bill) => (
              <li key={bill.auction_id}>
                <Link
                  to={`/mobile/bills/${encodeURIComponent(bill.auction_id)}`}
                  className="block rounded-md border border-border bg-surface/60 p-3.5 opacity-70"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-text">
                        {bill.farmer_name || 'अनाम कृषक'}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-muted">{bill.commodity}</p>
                    </div>
                    <span className="shrink-0 inline-flex items-center gap-1 rounded-sm bg-success/10 px-1.5 py-0.5 text-[10px] font-medium text-success">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M20 6 9 17l-5-5" />
                      </svg>
                      प्रिंट हो चुका
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!bills.length && (
        <p className="mt-10 text-center text-sm text-muted">कोई बिल नहीं। ऊपर से नया खोज करें।</p>
      )}
    </MobileLayout>
  )
}
