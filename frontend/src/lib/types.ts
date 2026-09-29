export interface Village {
  id: number
  name: string
  block?: string
  district?: string
}

export interface Commodity {
  id: number
  name: string
  code?: string
  unit: string
}

export interface Farmer {
  id: number
  name: string
  aadhaar: string
  mobile?: string
  village_id?: number | null
  village_name?: string | null
  land_area?: number | null
  bank_name?: string
  account_number?: string
  ifsc_code?: string
  created_at?: string
}

export interface Trader {
  id: number
  name: string
  gstin?: string
  pan?: string
  license_no?: string
  mobile?: string
  commission_rate: number
  created_at?: string
}

export interface ListResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface StockRow {
  commodity_id: number
  commodity_name: string
  segment: string
  qty: number
  avg_rate: number | null
  value: number
  bill_count: number
  last_date?: string | null
}

export interface StockTotals {
  commodities: number
  rows: number
  qty: number
  value: number
  avg_rate: number | null
}

export interface StockResponse {
  rows: StockRow[]
  totals: StockTotals
}

export interface StockSegmentSlice {
  name: string
  qty: number
  value: number
  bills: number
}

export interface StockCommoditySlice {
  name: string
  qty: number
  value: number
}

export interface StockTrendPoint {
  date: string
  qty: number
  value: number
}

export interface StockAnalytics {
  daily: StockTrendPoint[]
  by_segment: StockSegmentSlice[]
  by_commodity: StockCommoditySlice[]
  top_commodity: string | null
  total_value: number
  total_qty: number
}

export interface TraderStockRow {
  trader_id: number
  trader_name: string
  commodity_id: number
  commodity_name: string
  qty: number
  avg_rate: number | null
  value: number
  bill_count: number
  last_date?: string | null
}

export interface TraderStockResponse {
  rows: TraderStockRow[]
  totals: StockTotals
}
