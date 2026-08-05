import { api } from './client'

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

export function getDashboard() {
  return api.get<Dashboard>('/analytics/dashboard')
}

export function getTopProducts() {
  return api.get<ProductSales[]>('/analytics/top-products')
}

export function getCategoryProfit() {
  return api.get<CategoryProfit[]>('/analytics/category-profit')
}

export function getDeadStock() {
  return api.get<DeadStockItem[]>('/analytics/dead-stock')
}

export function getStockValue() {
  return api.get<StockValue>('/analytics/stock-value')
}
