import { api } from './client'

export interface Variant {
  id: number
  size: string
  color: string
  barcode: string | null
}

export interface Product {
  id: number
  name: string
  unit_code: string
  retail_price: string
  purchase_price: string | null
  margin: string | null
  sku: string
  barcode: string | null
  category_id: number | null
  min_stock: string
  photo: string
  variants: Variant[]
}

export interface Unit {
  code: string
  name: string
  fractional: boolean
}

export function listProducts(query = '') {
  const q = query ? `?query=${encodeURIComponent(query)}` : ''
  return api.get<Product[]>(`/products${q}`)
}

export function createProduct(input: {
  name: string
  unit_code?: string
  purchase_price?: string
  retail_price?: string
  sku?: string
  barcode?: string | null
  min_stock?: string
}) {
  return api.post<Product>('/products', input)
}

export function listUnits() {
  return api.get<Unit[]>('/products/units')
}
