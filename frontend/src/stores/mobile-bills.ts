import { create } from 'zustand'

import type { SummaryResponse, TodayBill } from '@/lib/mobile'

interface MobileBillsState {
  bills: TodayBill[]
  date: string
  summary: SummaryResponse | null
  printedIds: string[]
  setResults: (bills: TodayBill[], date: string) => void
  setSummary: (summary: SummaryResponse) => void
  markPrinted: (auctionId: string) => void
  clear: () => void
  find: (auctionId: string) => TodayBill | undefined
}

export const useMobileBills = create<MobileBillsState>()((set, get) => ({
  bills: [],
  date: '',
  summary: null,
  printedIds: [],
  setResults: (bills, date) => set({ bills, date }),
  setSummary: (summary) => set({ summary }),
  markPrinted: (auctionId: string) =>
    set((s) => ({
      printedIds: s.printedIds.includes(auctionId) ? s.printedIds : [...s.printedIds, auctionId],
    })),
  clear: () => set({ bills: [], date: '', summary: null, printedIds: [] }),
  find: (auctionId: string) => get().bills.find((b) => b.auction_id === auctionId),
}))
