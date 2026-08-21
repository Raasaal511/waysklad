const KEY_PREFIX = 'waysklad:restock-cart:'

export interface RestockCartState {
  ids: number[]
  quantities: Record<number, string>
}

const EMPTY: RestockCartState = { ids: [], quantities: {} }

export function loadRestockCart(warehouseId: number): RestockCartState {
  try {
    const raw = localStorage.getItem(KEY_PREFIX + warehouseId)
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
    localStorage.setItem(KEY_PREFIX + warehouseId, JSON.stringify(state))
  } catch {
    // приватный режим/квота — корзина просто не переживёт перезагрузку, не критично
  }
}
