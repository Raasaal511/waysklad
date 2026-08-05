import { api } from './client'

export type OrderStatus = 'new' | 'in_progress' | 'ready' | 'issued'

export interface OrderLine {
  product_id: number
  variant_id: number | null
  quantity: string
  price: string
  total: string
}

export interface Order {
  id: number
  client_id: number
  status: OrderStatus
  total: string
  prepayment: string
  to_pay: string
  due_date: string | null
  note: string
  lines: OrderLine[]
}

export interface OrderItemInput {
  product_id: number
  quantity: string
  price: string
  variant_id?: number | null
}

export function listActiveOrders() {
  return api.get<Order[]>('/orders')
}

export function getOrder(id: number) {
  return api.get<Order>(`/orders/${id}`)
}

export function createOrder(input: {
  client_id: number
  items: OrderItemInput[]
  due_date?: string | null
  prepayment?: string
  note?: string
}) {
  return api.post<Order>('/orders', input)
}

export function changeOrderStatus(id: number, newStatus: OrderStatus) {
  return api.patch<Order>(`/orders/${id}/status`, { new_status: newStatus })
}
