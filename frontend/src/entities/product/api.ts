import { api } from '../../shared/api/client'

export interface Variant {
  id: number
  size: string
  color: string
  barcode: string | null
  name: string
}

export interface VariantInput {
  id?: number | null
  size: string
  color: string
  barcode?: string | null
  name?: string
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
  description: string
  warranty_text: string
  storefront_photos: string[]
  show_on_storefront: boolean
  storefront_min_qty: string | null
  storefront_step_qty: string | null
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

export interface ProductHistoryEntry {
  id: number
  user_id: number
  user_name: string | null
  action: string
  entity: string
  entity_id: number | null
  details: Record<string, unknown>
  created_at: string
}

export type ImportMatchStatus = 'no_match' | 'match' | 'ambiguous_match'
export type ImportAction = 'create' | 'update' | 'skip'

export interface ExistingProductSnapshot {
  id: number
  name: string
  sku: string
  barcode: string | null
  unit_code: string
  purchase_price: string
  retail_price: string
  category_id: number | null
  min_stock: string
}

export interface DuplicateCandidate {
  matched_by: 'barcode' | 'sku' | 'name'
  product: ExistingProductSnapshot
}

export interface PreviewRow {
  row: number
  name: string
  sku: string
  barcode: string | null
  unit_code: string
  category_id: number | null
  purchase_price: string | null
  retail_price: string | null
  min_stock: string
  parse_error: string | null
  status: ImportMatchStatus
  candidates: DuplicateCandidate[]
}

export interface PreviewProductsResult {
  rows: PreviewRow[]
}

export interface ApplyImportRow {
  client_row_id: string
  action: ImportAction
  name: string
  sku: string
  barcode: string | null
  unit_code: string
  purchase_price: string
  retail_price: string
  category_id: number | null
  min_stock: string
  existing_product_id: number | null
}

export interface ApplyImportResult {
  created: number
  updated: number
  skipped: number
  errors: { client_row_id: string; message: string }[]
}

interface ProductInput {
  name: string
  unit_code?: string
  purchase_price?: string
  retail_price?: string
  sku?: string
  barcode?: string | null
  category_id?: number | null
  min_stock?: string
  description?: string
  warranty_text?: string
  show_on_storefront?: boolean
  storefront_min_qty?: string | null
  storefront_step_qty?: string | null
  variants?: VariantInput[]
  initial_stock_warehouse_id?: number | null
  initial_stock_quantity?: string | null
}

export function listCategories() {
  return api.get<Category[]>('/products/categories')
}

export function createCategory(input: { name: string; parent_id?: number | null }) {
  return api.post<Category>('/products/categories', input)
}

export interface ListProductsParams {
  query?: string
  limit?: number
  offset?: number
  categoryId?: number | null
  sort?: 'name' | 'price_asc' | 'price_desc' | 'margin_desc' | 'created_desc' | 'created_asc' | 'stock_desc'
  inStockOnly?: boolean
  warehouseId?: number | null
}

export async function listProducts(params: ListProductsParams = {}) {
  const search = new URLSearchParams()
  if (params.query) search.set('query', params.query)
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.offset != null) search.set('offset', String(params.offset))
  if (params.categoryId != null) search.set('category_id', String(params.categoryId))
  if (params.sort) search.set('sort', params.sort)
  if (params.inStockOnly) search.set('in_stock_only', 'true')
  if (params.warehouseId != null) search.set('warehouse_id', String(params.warehouseId))
  const qs = search.toString()
  const { data, total } = await api.getWithTotal<Product[]>(`/products${qs ? `?${qs}` : ''}`)
  return { items: data, total }
}

const ALL_PRODUCTS_PAGE_SIZE = 50

/** Весь каталог целиком (постранично, лимит на бэкенде — 50) — для форм выбора товара: продажа, заказ, приёмка. */
export async function listAllProducts(query = '', categoryId?: number | null) {
  const all: Product[] = []
  let offset = 0
  while (true) {
    const { items, total } = await listProducts({
      query,
      categoryId,
      limit: ALL_PRODUCTS_PAGE_SIZE,
      offset,
    })
    all.push(...items)
    offset += items.length
    if (items.length < ALL_PRODUCTS_PAGE_SIZE || offset >= total) break
  }
  return all
}

export function createProduct(input: ProductInput) {
  return api.post<Product>('/products', input)
}

export function getProduct(id: number) {
  return api.get<Product>(`/products/${id}`)
}

export function listUnits() {
  return api.get<Unit[]>('/products/units')
}

export function createUnit(input: { code: string; name: string; fractional?: boolean }) {
  return api.post<Unit>('/products/units', input)
}

export function getByBarcode(barcode: string) {
  return api.get<Product | null>(`/products/barcode/${encodeURIComponent(barcode)}`)
}

export function updateProduct(id: number, input: ProductInput & { photo?: string }) {
  return api.put<Product>(`/products/${id}`, input)
}

export function deleteProduct(id: number) {
  return api.delete<void>(`/products/${id}`)
}

export function generateBarcode() {
  return api.post<{ barcode: string }>('/products/barcode/generate')
}

export function setProductPhoto(productId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  return api.postForm<Product>(`/products/${productId}/photo`, form)
}

export function generateProductDescription(productId: number) {
  return api.post<{ description: string }>(`/products/${productId}/description/generate`)
}

export function addStorefrontPhoto(productId: number, file: File) {
  const form = new FormData()
  form.append('file', file)
  return api.postForm<Product>(`/products/${productId}/storefront-photos`, form)
}

export function setStorefrontPhotos(productId: number, photos: string[]) {
  return api.put<Product>(`/products/${productId}/storefront-photos`, { photos })
}

export function previewImport(file: File) {
  const form = new FormData()
  form.append('file', file)
  return api.postForm<PreviewProductsResult>('/products/import/preview', form)
}

export function applyImport(rows: ApplyImportRow[]) {
  return api.post<ApplyImportResult>('/products/import/apply', { rows })
}

export function getProductHistory(productId: number) {
  return api.get<ProductHistoryEntry[]>(`/products/${productId}/history`)
}

export type ExportFormat = 'xlsx' | 'csv' | 'pdf'

export function exportProducts(format: ExportFormat) {
  return api.getBlob(`/products/export.${format}`)
}
