import { api } from '../../shared/api/client'

export type MarketplaceSort = 'name' | 'price_asc' | 'price_desc' | 'created_desc'

export interface MarketplaceProduct {
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

export interface MarketplaceCatalog {
  products: MarketplaceProduct[]
  total: number
}

export interface MarketplaceParams {
  query?: string
  category?: string
  priceMin?: string
  priceMax?: string
  inStockOnly?: boolean
  variantSize?: string
  variantColor?: string
  shopSlug?: string
  sort?: MarketplaceSort
  limit?: number
  offset?: number
}

export function listMarketplaceProducts(params: MarketplaceParams = {}) {
  const search = new URLSearchParams()
  if (params.query) search.set('query', params.query)
  if (params.category) search.set('category', params.category)
  if (params.priceMin) search.set('price_min', params.priceMin)
  if (params.priceMax) search.set('price_max', params.priceMax)
  if (params.inStockOnly) search.set('in_stock_only', 'true')
  if (params.variantSize) search.set('variant_size', params.variantSize)
  if (params.variantColor) search.set('variant_color', params.variantColor)
  if (params.shopSlug) search.set('shop_slug', params.shopSlug)
  if (params.sort) search.set('sort', params.sort)
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.offset != null) search.set('offset', String(params.offset))
  const qs = search.toString()
  return api.get<MarketplaceCatalog>(`/marketplace/products${qs ? `?${qs}` : ''}`)
}
