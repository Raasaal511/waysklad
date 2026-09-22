import { api } from '../../shared/api/client'

export type MarketplaceSort =
  | 'name'
  | 'price_asc'
  | 'price_desc'
  | 'created_desc'
  | 'popular'
  | 'rating'
  | 'discount'

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
  platformCategory?: string
  priceMin?: string
  priceMax?: string
  inStockOnly?: boolean
  withDiscount?: boolean
  minRating?: number
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
  if (params.platformCategory) search.set('platform_category', params.platformCategory)
  if (params.priceMin) search.set('price_min', params.priceMin)
  if (params.priceMax) search.set('price_max', params.priceMax)
  if (params.inStockOnly) search.set('in_stock_only', 'true')
  if (params.withDiscount) search.set('with_discount', 'true')
  if (params.minRating) search.set('min_rating', String(params.minRating))
  if (params.variantSize) search.set('variant_size', params.variantSize)
  if (params.variantColor) search.set('variant_color', params.variantColor)
  if (params.shopSlug) search.set('shop_slug', params.shopSlug)
  if (params.sort) search.set('sort', params.sort)
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.offset != null) search.set('offset', String(params.offset))
  const qs = search.toString()
  return api.get<MarketplaceCatalog>(`/marketplace/products${qs ? `?${qs}` : ''}`)
}

export interface PlatformCategory {
  id: number
  slug: string
  name: string
  image: string
  parent_id: number | null
  products_count: number
}

export interface Banner {
  id: number
  placement: 'hero' | 'promo'
  title: string
  subtitle: string
  button_text: string
  link: string
  image: string
  image_mobile: string
  theme: 'light' | 'accent' | 'dark'
  sort_order: number
  is_active: boolean
  starts_at: string | null
  ends_at: string | null
  city: string | null
}

export interface ShopChip {
  slug: string
  name: string
  logo: string
  city: string | null
  is_verified: boolean
  average_rating: number
  reviews_count: number
  products_count: number
}

export type HomeSectionKey = 'discount' | 'popular' | 'new' | 'top_rated'

export interface HomeSection {
  key: HomeSectionKey
  title: string
  products: MarketplaceProduct[]
}

export interface MarketplaceHomeResponse {
  banners: { hero: Banner[]; promo: Banner[] }
  categories: PlatformCategory[]
  shops: ShopChip[]
  sections: HomeSection[]
  stats: { shops_count: number; products_count: number; cities_count: number }
}

export function getMarketplaceHome() {
  return api.get<MarketplaceHomeResponse>('/marketplace/home')
}

export function getMarketplaceCategories() {
  return api.get<{ categories: PlatformCategory[] }>('/marketplace/categories')
}

export interface MarketplaceShopsParams {
  query?: string
  sort?: 'popular' | 'rating' | 'new'
  limit?: number
  offset?: number
}

export function listMarketplaceShops(params: MarketplaceShopsParams = {}) {
  const search = new URLSearchParams()
  if (params.query) search.set('query', params.query)
  if (params.sort) search.set('sort', params.sort)
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.offset != null) search.set('offset', String(params.offset))
  const qs = search.toString()
  return api.get<{ shops: ShopChip[]; total: number }>(`/marketplace/shops${qs ? `?${qs}` : ''}`)
}
