export interface TodayBill {
  index: number
  auction_id: string
  auction_date: string
  farmer_name: string
  farmer_id: string
  farmer_mobile: string
  village: string
  comm_group: string
  commodity: string
  variety: string
  weight: number
  rate: number
  gross_amount: number
  hammali_rate: number
  hammali_amount: number
  toul_rate: number
  toul_amount: number
  payable: number
  gatepass_id: string
  gatepass_date: string
  grade: string
  mandi: string
  trader_id: string
  firm: string
}

export interface TodayBillsResponse {
  state: string
  date: string
  bills: TodayBill[]
}

export interface ApiState {
  state: string
  busy: boolean
  found_bills: number
  current_bill_id?: number | null
  show_captcha: boolean
  progress: string
  progress_events: { ts: string; message: string }[]
}

export interface PrintAnalysedResponse {
  state: string
  printed: boolean
}

export interface SummaryCropRow {
  commodity: string
  total_weight: number
  total_amount: number
  avg_rate: number
}

export interface SummaryStockRow {
  commodity: string
  total_weight: number
}

export interface SummaryMandiFee {
  total_bills: number
  total_quantity: number
  mandi_fee: number
  nirashrit_fee: number
}

export interface SummaryResponse {
  state: string
  date_range: { from: string; to: string }
  tax_paid_stock: SummaryStockRow[]
  crops: SummaryCropRow[]
  soyabean: SummaryCropRow | null
  mandi_fee_summary: SummaryMandiFee | null
  mandi_balance: number
  found_bills: number
}

const BASE = import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}/api/automation${path}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const msg = (data as { error?: { message?: string }; detail?: string }).error?.message
      ?? (data as { detail?: string }).detail
      ?? `Request failed (${res.status})`
    throw new Error(msg)
  }
  return (await res.json()) as T
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}/api/automation${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const msg = (data as { error?: { message?: string }; detail?: string }).error?.message
      ?? (data as { detail?: string }).detail
      ?? `Request failed (${res.status})`
    throw new Error(msg)
  }
  return (await res.json()) as T
}

export function searchTodayBills(): Promise<TodayBillsResponse> {
  return post<TodayBillsResponse>('/todays-bills')
}

export function getState(): Promise<ApiState> {
  return get<ApiState>('/state')
}

export function printAnalysedBill(
  auctionId: string,
  hammaliRate: number,
  toulRate: number,
): Promise<PrintAnalysedResponse> {
  return post<PrintAnalysedResponse>('/print-analysed', {
    auction_id: auctionId,
    printed_by: 'mobile',
    hammali_rate: hammaliRate,
    toul_rate: toulRate,
  })
}

export function printPortal(
  auctionId: string,
  hammaliAmount: number,
  toulRate: number,
): Promise<PrintAnalysedResponse> {
  return post<PrintAnalysedResponse>('/print-portal', {
    auction_id: auctionId,
    hammali_amount: hammaliAmount,
    toul_rate: toulRate,
  })
}

export function searchSummary(fromDate: string, toDate: string): Promise<SummaryResponse> {
  return post<SummaryResponse>('/summary', {
    from_date: fromDate,
    to_date: toDate,
  })
}

// ---------- Reports ----------

export interface GatepassRow {
  gatepass_id: string
  trader_name: string
  commodity: string
  weight: string
  taul_status: string
  payment_status: string
  mobile_no: string
  tol_pending: boolean
}

export interface ReportsResponse {
  state: string
  date: string
  total_gatepasses: number
  tol_pending_count: number
  gatepasses: GatepassRow[]
}

export function searchReports(): Promise<ReportsResponse> {
  return post<ReportsResponse>('/reports')
}

// ---------- Settings (admin-unlock protected) ----------

export interface AdminLoginResponse {
  access_token: string
  refresh_token: string
  user: { id: number; username: string; role?: string }
}

export interface MobileSetting {
  key: string
  value: string
  display_name?: string
  description?: string
  encrypted: boolean
  type: string
}

async function fetchWithBase<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const msg = (data as { error?: { message?: string }; detail?: string }).error?.message
      ?? (data as { detail?: string }).detail
      ?? `Request failed (${res.status})`
    throw new Error(msg)
  }
  return (await res.json()) as T
}

export function adminLogin(username: string, password: string): Promise<AdminLoginResponse> {
  return fetchWithBase<AdminLoginResponse>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function fetchSettings(token: string): Promise<{ items: Record<string, MobileSetting> }> {
  return fetchWithBase<{ items: Record<string, MobileSetting> }>('/api/settings', {
    headers: { Authorization: `Bearer ${token}` },
  })
}

export function updateSetting(token: string, key: string, value: string): Promise<MobileSetting> {
  return fetchWithBase<MobileSetting>(`/api/settings/${key}`, {
    method: 'PUT',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ value }),
  })
}
