// Офлайн-очередь (outbox) на сыром IndexedDB — без Dexie/idb, т.к. нужен
// один object store с 3 операциями (add/getAll/delete). Сейчас поддержаны
// только продажи (бэкенд POST /api/sync/sales умеет только их); при появлении
// других типов операций стор `sales` не переиспользуется — заводится свой.

import type { PaymentMethod, SaleItemInput } from '../../entities/sale/api'

const DB_NAME = 'waysklad-outbox'
const DB_VERSION = 1
const SALES_STORE = 'sales'

// Полезная нагрузка одной офлайн-продажи — соответствует телу POST /api/sync/sales
// (OfflineSaleRequest на бэкенде), но без обёртки { sales: [...] }.
export interface QueuedSale {
  client_op_id: string
  warehouse_id: number
  payment_method: PaymentMethod
  items: SaleItemInput[]
  discount: string
  client_id: number | null
  cash_received: string | null
  change_kept: string | null
  debt_due_date: string | null
  queued_at: string
}

export type NewQueuedSale = Omit<QueuedSale, 'client_op_id' | 'queued_at'>

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(SALES_STORE)) {
        db.createObjectStore(SALES_STORE, { keyPath: 'client_op_id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function withStore<T>(
  mode: IDBTransactionMode,
  fn: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const db = await openDb()
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(SALES_STORE, mode)
      const request = fn(tx.objectStore(SALES_STORE))
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })
  } finally {
    db.close()
  }
}

// Сохранить продажу в очередь на отправку. client_op_id генерируется здесь же —
// сервер использует его для идемпотентности (повторная отправка не задвоит продажу).
export async function queueSale(sale: NewQueuedSale): Promise<QueuedSale> {
  const queued: QueuedSale = {
    ...sale,
    client_op_id: crypto.randomUUID(),
    queued_at: new Date().toISOString(),
  }
  await withStore('readwrite', (store) => store.add(queued))
  return queued
}

export async function getQueuedSales(): Promise<QueuedSale[]> {
  return withStore('readonly', (store) => store.getAll())
}

export async function removeQueuedSale(clientOpId: string): Promise<void> {
  await withStore('readwrite', (store) => store.delete(clientOpId))
}

export async function countQueuedSales(): Promise<number> {
  return withStore('readonly', (store) => store.count())
}
