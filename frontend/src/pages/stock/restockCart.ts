import { scopedKey } from '../../shared/lib/scopedStorage'

export interface RestockCartState {
  ids: number[]
  quantities: Record<number, string>
}

const EMPTY: RestockCartState = { ids: [], quantities: {} }

// scopedKey уже несёт user_id — warehouseId сверху разделяет корзины
// разных складов ОДНОГО пользователя, а не разных пользователей.
function key(warehouseId: number): string {
  return `${scopedKey('restock-cart')}:${warehouseId}`
}

export function loadRestockCart(warehouseId: number): RestockCartState {
  try {
    const raw = localStorage.getItem(key(warehouseId))
    if (!raw) return EMPTY
    const parsed = JSON.parse(raw)
    return {
      ids: Array.isArray(parsed.ids) ? parsed.ids : [],
      quantities: parsed.quantities && typeof parsed.quantities === 'object' ? parsed.quantities : {},
    }
  } catch {
    return EMPTY
  }
}

export function saveRestockCart(warehouseId: number, state: RestockCartState): void {
  try {
    localStorage.setItem(key(warehouseId), JSON.stringify(state))
  } catch {
    // приватный режим/квота — корзина просто не переживёт перезагрузку, не критично
  }
}

/** Best-effort подчистка при logout(): scopedKey уже изолирует корзины по
 * пользователю сам по себе (реальная защита), это лишь убирает разросшийся
 * localStorage — старые ключи от версии кода до скоупинга и ключи из
 * прошлых сессий, которые больше никто не запросит. */
export function clearAllRestockCarts(): void {
  try {
    for (const storageKey of Object.keys(localStorage)) {
      if (storageKey.includes(':restock-cart:')) localStorage.removeItem(storageKey)
    }
  } catch {
    // ignore
  }
}
