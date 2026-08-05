import { api } from './client'

export interface Warehouse {
  id: number
  name: string
  address: string
}

export interface StockItem {
  product_id: number
  variant_id: number | null
  warehouse_id: number
  quantity: string
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

export function listWarehouses() {
  return api.get<Warehouse[]>('/inventory/warehouses')
}

export function createWarehouse(input: { name: string; address?: string }) {
  return api.post<Warehouse>('/inventory/warehouses', input)
}

export function listStock() {
  return api.get<StockItem[]>('/inventory/stock')
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
