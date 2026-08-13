import { useCallback, useEffect, useRef, useState } from 'react'
import { syncSales } from '../../entities/sale/api'
import { getQueuedSales, removeQueuedSale } from './outbox'

export interface OfflineSyncNotice {
  kind: 'success' | 'error'
  message: string
}

// Синхронизация офлайн-очереди продаж: при появлении сети (событие online) и при
// старте приложения (вдруг сеть появилась, пока вкладка была закрыта) шлём накопленные
// продажи одним батчем в POST /api/sync/sales. Идемпотентность по client_op_id — сервер
// не задвоит продажу, если её уже применили в прошлой попытке (см. ApplyOfflineSalesUseCase).
export function useOfflineSync() {
  const [pendingCount, setPendingCount] = useState(0)
  const [notice, setNotice] = useState<OfflineSyncNotice | null>(null)
  const syncingRef = useRef(false)

  const refreshCount = useCallback(() => {
    getQueuedSales().then((sales) => setPendingCount(sales.length)).catch(() => {})
  }, [])

  const sync = useCallback(async () => {
    if (syncingRef.current || !navigator.onLine) return
    syncingRef.current = true
    try {
      const queued = await getQueuedSales()
      if (queued.length === 0) return

      const response = await syncSales(
        queued.map(({ queued_at: _queued_at, ...sale }) => sale),
      )

      for (const applied of response.applied) {
        if (applied.client_op_id) await removeQueuedSale(applied.client_op_id)
      }
      // Ошибка бизнес-правила (например, остаток кончился, пока были офлайн) —
      // операцию из очереди убираем всё равно: повторная отправка её не исправит,
      // а зависшая запись будет вечно блестеть счётчиком неотправленных продаж.
      for (const err of response.errors) {
        if (err.client_op_id) await removeQueuedSale(err.client_op_id)
      }

      if (response.applied.length > 0) {
        setNotice({
          kind: 'success',
          message: `Синхронизировано отложенных продаж: ${response.applied.length}`,
        })
      }
      if (response.errors.length > 0) {
        setNotice({
          kind: 'error',
          message: `Не удалось применить ${response.errors.length} отложенных продаж: ${response.errors[0].message}`,
        })
      }
    } catch {
      // сеть моргнула повторно или сервер недоступен — тихо, попробуем при следующем online
    } finally {
      syncingRef.current = false
      refreshCount()
    }
  }, [refreshCount])

  useEffect(() => {
    refreshCount()
    sync()
    window.addEventListener('online', sync)
    return () => window.removeEventListener('online', sync)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { pendingCount, notice, dismissNotice: () => setNotice(null), refreshCount, syncNow: sync }
}
