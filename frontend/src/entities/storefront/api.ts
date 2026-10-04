import { api } from '../../shared/api/client'
import type { Order } from '../order/api'

export type StorefrontRequestStatus = 'new' | 'accepted' | 'rejected'
export type StorefrontMessageAuthor = 'customer' | 'staff'
export type StorefrontSort = 'name' | 'price_asc' | 'price_desc' | 'created_desc'

export type StockLevel = 'out' | 'low' | 'in'

export interface StorefrontProduct {
  id: number
  name: string
  retail_price: string
  old_price?: string | null
  discount_percent?: number | null
  photo: string
  category_id: number | null
  in_stock: boolean
  sold_count?: string
  min_order_qty: string | null
  order_step_qty: string | null
  average_rating: number
  reviews_count: number
}

export interface StorefrontVariant {
  id: number
  size: string
  color: string
  photo: string
  price: string | null
  name: string
  display_name: string
  in_stock: boolean
  stock_level: StockLevel
  stock_qty: string | null
}

export interface StorefrontProductCategory {
  id: number
  name: string
  parent: { id: number; name: string } | null
}

export interface StorefrontProductShop {
  slug: string
  name: string
  logo: string
  average_rating: number
  reviews_count: number
}

export interface StorefrontProductDetail extends StorefrontProduct {
  sku: string
  description: string
  storefront_photos: string[]
  variants: StorefrontVariant[]
  warranty_text: string
  stock_level: StockLevel
  stock_qty: string | null
  category: StorefrontProductCategory | null
  unit_code: string
  unit_label: string
  views_90d: number
  shop: StorefrontProductShop
}

export interface StorefrontCategory {
  id: number
  name: string
  parent_id: number | null
  product_count: number
}

export interface StorefrontWarehouse {
  id: number
  name: string
  address: string
}

export interface StorefrontCatalog {
  shop_name: string
  products: StorefrontProduct[]
  categories: StorefrontCategory[]
  warehouses: StorefrontWarehouse[]
  available_sizes: string[]
  available_colors: string[]
  total: number
  min_order_total: string | null
}

export interface StorefrontProductPage {
  shop_name: string
  product: StorefrontProductDetail
}

export interface StorefrontProfileRating {
  average_rating: number
  reviews_count: number
}

export interface StorefrontProfileContacts {
  phone: string
  whatsapp: string
  telegram: string
}

export interface StorefrontProfileAddress {
  name: string
  address: string
}

export interface StorefrontProfilePolicies {
  refund_money: string | null
  payment: string | null
  delivery: string | null
  returns: string | null
}

export interface StorefrontShopProfile {
  name: string
  slug: string
  logo: string
  description: string
  on_platform_since: string
  rating: StorefrontProfileRating
  products_count: number
  orders_count: number | null
  orders_count_label: string | null
  min_order_total: string | null
  contacts: StorefrontProfileContacts
  addresses: StorefrontProfileAddress[]
  policies: StorefrontProfilePolicies
}

export type SimilarScope = 'shop' | 'marketplace'

export interface SimilarMarketplaceProduct {
  id: number
  name: string
  retail_price: string
  photo: string
  category_name: string | null
  in_stock: boolean
  min_order_qty: string | null
  order_step_qty: string | null
  shop_slug: string
  shop_name: string
  sold_count: string
  average_rating: number
  reviews_count: number
  shop_logo: string
  shop_is_verified: boolean
  shop_city: string | null
  old_price: string | null
  discount_percent: number | null
  is_new: boolean
  is_hit: boolean
}

export interface SimilarProductsResponse {
  shop_products: StorefrontProduct[]
  marketplace_products: SimilarMarketplaceProduct[]
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
  insufficient_stock_at_request: boolean
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
  minPrice?: string
  maxPrice?: string
  inStockOnly?: boolean
  variantSize?: string
  variantColor?: string
  /** «от N звёзд» — backend уже поддерживает (StorefrontCatalogParams.min_rating), 1..5. */
  minRating?: number | null
}

function catalogQuery(params: CatalogParams) {
  const search = new URLSearchParams()
  if (params.query) search.set('query', params.query)
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.offset != null) search.set('offset', String(params.offset))
  if (params.categoryId != null) search.set('category_id', String(params.categoryId))
  if (params.warehouseId != null) search.set('warehouse_id', String(params.warehouseId))
  if (params.sort) search.set('sort', params.sort)
  if (params.minPrice) search.set('min_price', params.minPrice)
  if (params.maxPrice) search.set('max_price', params.maxPrice)
  if (params.inStockOnly) search.set('in_stock_only', 'true')
  if (params.variantSize) search.set('variant_size', params.variantSize)
  if (params.variantColor) search.set('variant_color', params.variantColor)
  if (params.minRating != null) search.set('min_rating', String(params.minRating))
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

export function getStorefrontShopProfile(slug: string) {
  return api.get<StorefrontShopProfile>(`/storefront/${encodeURIComponent(slug)}/profile`)
}

// Профиль магазина запрашивают одновременно PublicHeader (имя для плейсхолдера
// поиска) и страница каталога/товара (вся карточка магазина) — общий кэш +
// дедупликация одновременных запросов, чтобы это не превращалось в два похода
// на сервер за одним и тем же (P7 п.2, не больше 4 запросов на карточке товара).
const shopProfileCache = new Map<string, StorefrontShopProfile>()
const shopProfileInflight = new Map<string, Promise<StorefrontShopProfile>>()

export function getStorefrontShopProfileCached(slug: string): Promise<StorefrontShopProfile> {
  const cached = shopProfileCache.get(slug)
  if (cached) return Promise.resolve(cached)
  const inflight = shopProfileInflight.get(slug)
  if (inflight) return inflight
  const request = getStorefrontShopProfile(slug)
    .then((data) => {
      shopProfileCache.set(slug, data)
      shopProfileInflight.delete(slug)
      return data
    })
    .catch((err) => {
      shopProfileInflight.delete(slug)
      throw err
    })
  shopProfileInflight.set(slug, request)
  return request
}

export function peekCachedStorefrontShopProfile(slug: string): StorefrontShopProfile | null {
  return shopProfileCache.get(slug) ?? null
}

/** Фиксирует просмотр карточки товара. Не бросает — вызывающий код не должен падать из-за метрики. */
export async function trackProductView(slug: string, productId: number): Promise<void> {
  try {
    await api.post<void>(`/storefront/${encodeURIComponent(slug)}/products/${productId}/view`)
  } catch {
    // просмотры — не критичная метрика, тихо игнорируем сбой
  }
}

export function getSimilarProducts(slug: string, productId: number, scope: SimilarScope, limit = 10) {
  return api.get<SimilarProductsResponse>(
    `/storefront/${encodeURIComponent(slug)}/products/${productId}/similar?scope=${scope}&limit=${limit}`,
  )
}

export function createStorefrontRequest(
  slug: string,
  input: {
    /** Не передаём — сервер возьмёт имя из профиля покупателя (иначе логин, телефон). */
    customer_name?: string
    note?: string
    items: { product_id: number; quantity: string; variant_id?: number | null }[]
  },
  customerAccessToken: string,
) {
  return api.post<StorefrontRequestCreated>(
    `/storefront/${encodeURIComponent(slug)}/requests`,
    input,
    { headers: { Authorization: `Bearer ${customerAccessToken}` } },
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

/** Минимальное стартовое количество с учётом min/step. */
export function initialOrderQty(min: string | null | undefined, _step: string | null | undefined): number {
  const minN = min != null && min !== '' ? Number(min) : 1
  const base = Number.isFinite(minN) && minN > 0 ? minN : 1
  return base
}

export function bumpOrderQty(
  current: number,
  deltaSteps: number,
  min: string | null | undefined,
  step: string | null | undefined,
): number {
  const minN = min != null && min !== '' && Number(min) > 0 ? Number(min) : 1
  const stepN = step != null && step !== '' && Number(step) > 0 ? Number(step) : 1
  const next = current + deltaSteps * stepN
  return Math.max(minN, Math.min(9999, next))
}
