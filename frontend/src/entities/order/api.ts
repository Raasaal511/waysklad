import { api } from '../../shared/api/client'
import type { PaymentMethod, Sale } from '../sale/api'

export type OrderStatus = 'new' | 'in_progress' | 'ready' | 'issued' | 'cancelled'
export type OrderSource = 'whatsapp' | 'instagram' | 'call' | 'in_person' | 'storefront'

export interface OrderLine {
  product_id: number
  variant_id: number | null
  quantity: string
  price: string
  total: string
}

export interface Order {
  id: number
  number: number | null
  client_id: number
  warehouse_id: number
  status: OrderStatus
  source: OrderSource
  total: string
  prepayment: string
  to_pay: string
  due_date: string | null
  note: string
  sale_id: number | null
  created_at: string | null
  lines: OrderLine[]
}

export interface OrderItemInput {
  product_id: number
  quantity: string
  price: string
  variant_id?: number | null
}

export interface OrderFormInput {
  client_id: number
  warehouse_id: number
  items: OrderItemInput[]
  due_date: string
  prepayment?: string
  source?: OrderSource
  note?: string
}

export interface IssueOrderResult {
  order: Order
  sale: Sale
}

export function listActiveOrders() {
  return api.get<Order[]>('/orders')
}

export function listCompletedOrders() {
  return api.get<Order[]>('/orders/completed')
}

export function getOrder(id: number) {
  return api.get<Order>(`/orders/${id}`)
}

export function createOrder(input: OrderFormInput) {
  return api.post<Order>('/orders', input)
}

export function updateOrder(id: number, input: OrderFormInput) {
  return api.patch<Order>(`/orders/${id}`, input)
}

export function changeOrderStatus(id: number, newStatus: OrderStatus) {
  return api.patch<Order>(`/orders/${id}/status`, { new_status: newStatus })
}

export function cancelOrder(id: number, reason?: string) {
  return api.post<Order>(`/orders/${id}/cancel`, { reason: reason ?? '' })
}

export function issueOrder(
  id: number,
  input: {
    payment_method: PaymentMethod
    cash_received?: string | null
    change_kept?: string | null
    debt_due_date?: string | null
    paid_now?: string | null
  },
) {
  return api.post<IssueOrderResult>(`/orders/${id}/issue`, input)
}

export interface OrderHistoryEntry {
  id: number
  user_id: number
  user_name: string | null
  action: string
  entity: string
  entity_id: number | null
  details: Record<string, unknown>
  created_at: string
}

export function getOrderHistory(id: number) {
  return api.get<OrderHistoryEntry[]>(`/orders/${id}/history`)
}
