import { api } from '../../shared/api/client'

export interface Warehouse {
  id: number
  name: string
  address: string
  assigned_user_ids: number[]
}

export interface StockItem {
  product_id: number
  variant_id: number | null
  warehouse_id: number
  quantity: string
  reserved: string
  available: string
}

export interface StockLine {
  product_id: number
  quantity: string
  variant_id?: number | null
  cost?: string | null
}

export interface StockDocument {
  id: number
  type: string
  warehouse_id: number
  to_warehouse_id: number | null
  note: string
}

export interface DocumentLine {
  product_id: number
  variant_id: number | null
  quantity: string
  cost: string | null
}

export interface DocumentHistoryEntry {
  id: number
  number: number
  type: 'receipt' | 'write_off' | 'transfer' | 'stocktake'
  warehouse_id: number
  to_warehouse_id: number | null
  author_id: number
  note: string
  created_at: string
  lines: DocumentLine[]
}

export interface RestockRecommendation {
  product_id: number
  product_name: string
  quantity: string
  min_stock: string
  quantity_sold: string
}

export function getRestockRecommendations(warehouseId?: number) {
  const query = warehouseId != null ? `?warehouse_id=${warehouseId}` : ''
  return api.get<RestockRecommendation[]>(`/inventory/restock-recommendations${query}`)
}

export function listWarehouses() {
  return api.get<Warehouse[]>('/inventory/warehouses')
}

export function createWarehouse(input: {
  name: string
  address?: string
  assigned_user_ids?: number[]
}) {
  return api.post<Warehouse>('/inventory/warehouses', input)
}

export function setWarehouseAssignments(warehouseId: number, userIds: number[]) {
  return api.put<Warehouse>(`/inventory/warehouses/${warehouseId}/assignments`, {
    user_ids: userIds,
  })
}

export function updateWarehouseDetails(warehouseId: number, input: { name: string; address?: string }) {
  return api.put<Warehouse>(`/inventory/warehouses/${warehouseId}`, input)
}

export function listStock() {
  return api.get<StockItem[]>('/inventory/stock')
}

export function listDocuments() {
  return api.get<DocumentHistoryEntry[]>('/inventory/documents')
}

export type ExportFormat = 'xlsx' | 'csv' | 'pdf'

export function exportDocuments(format: ExportFormat) {
  return api.getBlob(`/inventory/documents/export.${format}`)
}

export function receiveGoods(input: { warehouse_id: number; lines: StockLine[]; note?: string }) {
  return api.post<StockDocument>('/inventory/receive', input)
}

export function writeOff(input: { warehouse_id: number; lines: StockLine[]; note?: string }) {
  return api.post<StockDocument>('/inventory/write-off', input)
}

export function transferStock(input: {
  warehouse_id: number
  to_warehouse_id: number
  lines: StockLine[]
  note?: string
}) {
  return api.post<StockDocument>('/inventory/transfer', input)
}
