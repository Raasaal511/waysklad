import { api } from '../../shared/api/client'

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
  warehouse_id: number
  seller_id: number
  payment_method: PaymentMethod
  subtotal: string
  discount: string
  total: string
  change: string | null
  cash_received: string | null
  client_id: number | null
  created_at: string
  note: string
  deleted_at: string | null
  order_id: number | null
  lines: SaleLine[]
}

export interface ListSalesParams {
  limit?: number
  offset?: number
  clientId?: number | null
  warehouseId?: number | null
  paymentMethod?: PaymentMethod | 'all'
  dateFrom?: string | null
  dateTo?: string | null
  sort?: 'date_desc' | 'date_asc' | 'payment'
}

export async function listSales(params: ListSalesParams = {}) {
  const search = new URLSearchParams()
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.offset != null) search.set('offset', String(params.offset))
  if (params.clientId != null) search.set('client_id', String(params.clientId))
  if (params.warehouseId != null) search.set('warehouse_id', String(params.warehouseId))
  if (params.paymentMethod && params.paymentMethod !== 'all') search.set('payment_method', params.paymentMethod)
  if (params.dateFrom) search.set('date_from', params.dateFrom)
  if (params.dateTo) search.set('date_to', params.dateTo)
  if (params.sort) search.set('sort', params.sort)
  const qs = search.toString()
  const { data, total } = await api.getWithTotal<Sale[]>(`/sales${qs ? `?${qs}` : ''}`)
  return { items: data, total }
}

export interface SalesSummaryParams {
  warehouseId?: number | null
  dateFrom?: string | null
  dateTo?: string | null
}

export interface SalesSummary {
  by_payment_method: Partial<Record<PaymentMethod, { count: number; total: string }>>
}

export function getSalesSummary(params: SalesSummaryParams = {}) {
  const search = new URLSearchParams()
  if (params.warehouseId != null) search.set('warehouse_id', String(params.warehouseId))
  if (params.dateFrom) search.set('date_from', params.dateFrom)
  if (params.dateTo) search.set('date_to', params.dateTo)
  const qs = search.toString()
  return api.get<SalesSummary>(`/sales/summary${qs ? `?${qs}` : ''}`)
}

export function getSale(saleId: number) {
  return api.get<Sale>(`/sales/${saleId}`)
}

export function editSale(saleId: number, input: { client_id: number | null; note: string }) {
  return api.patch<Sale>(`/sales/${saleId}`, input)
}

export function deleteSale(saleId: number) {
  return api.delete<void>(`/sales/${saleId}`)
}

export interface SaleHistoryEntry {
  id: number
  user_id: number
  user_name: string | null
  action: string
  entity: string
  entity_id: number | null
  details: Record<string, unknown>
  created_at: string
}

export function getSaleHistory(saleId: number) {
  return api.get<SaleHistoryEntry[]>(`/sales/${saleId}/history`)
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
  debt_due_date?: string | null
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

export function listSaleReturns(saleId: number) {
  return api.get<SaleReturn[]>(`/sales/${saleId}/returns`)
}

export interface Receipt {
  text: string
  whatsapp_link: string | null
}

export function getReceipt(saleId: number) {
  return api.get<Receipt>(`/sales/${saleId}/receipt`)
}

export function getReceiptPdf(saleId: number) {
  return api.getBlob(`/sales/${saleId}/receipt.pdf`)
}

// Синхронизация офлайн-очереди — см. shared/offline/outbox.ts
export interface OfflineSaleInput {
  client_op_id: string
  warehouse_id: number
  payment_method: PaymentMethod
  items: SaleItemInput[]
  discount?: string
  client_id?: number | null
  cash_received?: string | null
}

export interface AppliedOfflineSale {
  client_op_id: string | null
  id: number
  total: string
  created_at: string
}

export interface SyncSalesError {
  client_op_id: string | null
  message: string
}

export interface SyncSalesResponse {
  applied: AppliedOfflineSale[]
  errors: SyncSalesError[]
}

export function syncSales(sales: OfflineSaleInput[]) {
  return api.post<SyncSalesResponse>('/sync/sales', { sales })
}
