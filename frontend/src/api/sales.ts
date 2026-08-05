import { api } from './client'

export type PaymentMethod = 'cash' | 'transfer' | 'credit'

export interface SaleLine {
  id: number
  product_id: number
  variant_id: number | null
  quantity: string
  price: string
  total: string
}

export interface Sale {
  id: number
  payment_method: PaymentMethod
  subtotal: string
  discount: string
  total: string
  change: string | null
  client_id: number | null
  created_at: string
  lines: SaleLine[]
}

export interface SaleItemInput {
  product_id: number
  quantity: string
  price: string
  variant_id?: number | null
}

export function createSale(input: {
  warehouse_id: number
  payment_method: PaymentMethod
  items: SaleItemInput[]
  discount?: string
  client_id?: number | null
  cash_received?: string | null
}) {
  return api.post<Sale>('/sales', input)
}

export interface SaleReturn {
  id: number
  sale_id: number
  note: string
  refund: string
  created_at: string
  lines: { sale_line_id: number; quantity: string }[]
}

export function returnSale(
  saleId: number,
  input: { items: { sale_line_id: number; quantity: string }[]; note?: string },
) {
  return api.post<SaleReturn>(`/sales/${saleId}/returns`, input)
}
