import { api } from '../../shared/api/client'

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

export interface Category {
  id: number
  name: string
  parent_id: number | null
}

export function listCategories() {
  return api.get<Category[]>('/products/categories')
}

export function createCategory(input: { name: string; parent_id?: number | null }) {
  return api.post<Category>('/products/categories', input)
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

export function getByBarcode(barcode: string) {
  return api.get<Product | null>(`/products/barcode/${encodeURIComponent(barcode)}`)
}

export function updateProduct(
  id: number,
  input: {
    name: string
    unit_code?: string
    purchase_price?: string
    retail_price?: string
    sku?: string
    barcode?: string | null
    min_stock?: string
  },
) {
  return api.put<Product>(`/products/${id}`, input)
}
