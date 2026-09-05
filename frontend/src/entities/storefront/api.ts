import { api } from '../../shared/api/client'
import type { Order } from '../order/api'

export type StorefrontRequestStatus = 'new' | 'accepted' | 'rejected'
export type StorefrontMessageAuthor = 'customer' | 'staff'
export type StorefrontSort = 'name' | 'price_asc' | 'price_desc' | 'created_desc'

export interface StorefrontProduct {
  id: number
  name: string
  retail_price: string
  photo: string
  category_id: number | null
  in_stock: boolean
}

export interface StorefrontProductDetail extends StorefrontProduct {
  sku: string
  variants: { id: number; size: string; color: string }[]
}

export interface StorefrontCategory {
  id: number
  name: string
  parent_id: number | null
  product_count: number
}

export interface StorefrontCatalog {
  shop_name: string
  products: StorefrontProduct[]
  categories: StorefrontCategory[]
  total: number
}

export interface StorefrontProductPage {
  shop_name: string
  product: StorefrontProductDetail
}

export interface StorefrontRequestLine {
  product_id: number
  quantity: string
  variant_id: number | null
}

export interface StorefrontRequest {
  id: number
  customer_name: string
  customer_phone: string
  note: string
  status: StorefrontRequestStatus
  lines: StorefrontRequestLine[]
}

export interface StorefrontRequestCreated extends StorefrontRequest {
  access_token: string
}

export interface StorefrontMessage {
  id: number
  request_id: number
  author: StorefrontMessageAuthor
  text: string
  created_at: string | null
}

export interface StorefrontRequestOrderSummary {
  due_date: string
  total: string
  prepayment: string
  to_pay: string
  status: string
}

export interface StorefrontRequestStatusResponse {
  status: StorefrontRequestStatus
  order: StorefrontRequestOrderSummary | null
}

export interface CatalogParams {
  query?: string
  limit?: number
  offset?: number
  categoryId?: number | null
  warehouseId?: number | null
  sort?: StorefrontSort
}

function catalogQuery(params: CatalogParams) {
  const search = new URLSearchParams()
  if (params.query) search.set('query', params.query)
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.offset != null) search.set('offset', String(params.offset))
  if (params.categoryId != null) search.set('category_id', String(params.categoryId))
  if (params.warehouseId != null) search.set('warehouse_id', String(params.warehouseId))
  if (params.sort) search.set('sort', params.sort)
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export function getStorefrontCatalog(slug: string, params: CatalogParams = {}) {
  return api.get<StorefrontCatalog>(`/storefront/${encodeURIComponent(slug)}${catalogQuery(params)}`)
}

export function getStorefrontProduct(slug: string, productId: number) {
  return api.get<StorefrontProductPage>(
    `/storefront/${encodeURIComponent(slug)}/products/${productId}`,
  )
}

export function createStorefrontRequest(
  slug: string,
  input: {
    customer_name: string
    customer_phone?: string
    note?: string
    items: { product_id: number; quantity: string; variant_id?: number | null }[]
  },
) {
  return api.post<StorefrontRequestCreated>(
    `/storefront/${encodeURIComponent(slug)}/requests`,
    input,
  )
}

export function getStorefrontRequestStatus(token: string) {
  return api.get<StorefrontRequestStatusResponse>(
    `/storefront/requests/status?token=${encodeURIComponent(token)}`,
  )
}

export function listStorefrontChat(token: string) {
  return api.get<StorefrontMessage[]>(`/storefront/requests/chat?token=${encodeURIComponent(token)}`)
}

export function sendStorefrontChat(token: string, text: string) {
  return api.post<StorefrontMessage>(`/storefront/requests/chat?token=${encodeURIComponent(token)}`, {
    text,
  })
}

export function listNewStorefrontRequests() {
  return api.get<StorefrontRequest[]>('/storefront/requests/new')
}

export function getStorefrontRequest(id: number) {
  return api.get<StorefrontRequest>(`/storefront/requests/${id}`)
}

export function acceptStorefrontRequest(
  id: number,
  input: { warehouse_id: number; due_date: string; prepayment?: string },
) {
  return api.post<Order>(`/storefront/requests/${id}/accept`, input)
}

export function rejectStorefrontRequest(id: number) {
  return api.post<StorefrontRequest>(`/storefront/requests/${id}/reject`)
}

export function listStaffStorefrontChat(requestId: number) {
  return api.get<StorefrontMessage[]>(`/storefront/requests/${requestId}/chat`)
}

export function sendStaffStorefrontChat(requestId: number, text: string) {
  return api.post<StorefrontMessage>(`/storefront/requests/${requestId}/chat`, { text })
}

const REQUEST_TOKEN_KEY = 'waysklad:storefront-request-token'

export function saveRequestToken(slug: string, token: string) {
  localStorage.setItem(`${REQUEST_TOKEN_KEY}:${slug}`, token)
}

export function loadRequestToken(slug: string): string | null {
  return localStorage.getItem(`${REQUEST_TOKEN_KEY}:${slug}`)
}

export function storefrontChatWsUrl(token: string): string {
  const apiBase = import.meta.env.VITE_API_URL ?? '/api'
  if (apiBase.startsWith('http')) {
    const wsBase = apiBase.replace(/^http/, 'ws')
    return `${wsBase}/storefront/requests/chat/ws?token=${encodeURIComponent(token)}`
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${apiBase}/storefront/requests/chat/ws?token=${encodeURIComponent(token)}`
}
