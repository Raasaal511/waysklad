import { api } from '../../shared/api/client'

export interface PeriodTotals {
  sales_count: number
  revenue: string
  profit: string
}

export interface Dashboard {
  today: PeriodTotals
  week: PeriodTotals
  month: PeriodTotals
}

export interface ProductSales {
  product_id: number
  product_name: string
  quantity_sold: string
  revenue: string
}

export interface CategoryProfit {
  category_id: number | null
  category_name: string
  revenue: string
  profit: string
}

export interface DeadStockItem {
  product_id: number
  product_name: string
  quantity: string
  purchase_price: string
  last_sale_at: string | null
}

export interface StockValueItem {
  product_id: number
  product_name: string
  quantity: string
  purchase_price: string
  value: string
}

export interface StockValue {
  total_value: string
  items: StockValueItem[]
}

export type TimelineBucket = 'day' | 'week' | 'month'

export interface TimelinePoint {
  bucket_start: string
  sales_count: number
  revenue: string
  profit: string
}

export interface AnalyticsPeriodParams {
  dateFrom?: string
  dateTo?: string
}

function periodQuery(params: AnalyticsPeriodParams = {}): string {
  const search = new URLSearchParams()
  if (params.dateFrom) search.set('date_from', params.dateFrom)
  if (params.dateTo) search.set('date_to', params.dateTo)
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export function getDashboard() {
  return api.get<Dashboard>('/analytics/dashboard')
}

export function getPeriodTotals(params: AnalyticsPeriodParams = {}) {
  return api.get<PeriodTotals>(`/analytics/totals${periodQuery(params)}`)
}

export function getTopProducts(params: AnalyticsPeriodParams = {}) {
  return api.get<ProductSales[]>(`/analytics/top-products${periodQuery(params)}`)
}

export function getCategoryProfit(params: AnalyticsPeriodParams = {}) {
  return api.get<CategoryProfit[]>(`/analytics/category-profit${periodQuery(params)}`)
}

export function getRevenueTimeline(params: AnalyticsPeriodParams & { bucket?: TimelineBucket } = {}) {
  const search = new URLSearchParams()
  if (params.dateFrom) search.set('date_from', params.dateFrom)
  if (params.dateTo) search.set('date_to', params.dateTo)
  if (params.bucket) search.set('bucket', params.bucket)
  const qs = search.toString()
  return api.get<TimelinePoint[]>(`/analytics/timeline${qs ? `?${qs}` : ''}`)
}

export function getDeadStock() {
  return api.get<DeadStockItem[]>('/analytics/dead-stock')
}

export function getStockValue() {
  return api.get<StockValue>('/analytics/stock-value')
}
