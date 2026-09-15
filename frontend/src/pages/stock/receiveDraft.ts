import { scopedKey } from '../../shared/lib/scopedStorage'

export interface ReceiveDraft {
  warehouseId: number
  lines: { productId: number; quantity: string }[]
  /** Если приёмка открыта из задачи на дозаказ — id задачи, которую нужно перевести в «done»
   * после сохранения приёмки. */
  fromTaskId?: number
}

export function loadReceiveDraft(): ReceiveDraft | null {
  try {
    const raw = localStorage.getItem(scopedKey('receive-draft'))
    return raw ? (JSON.parse(raw) as ReceiveDraft) : null
  } catch {
    return null
  }
}

export function saveReceiveDraft(draft: ReceiveDraft): void {
  try {
    localStorage.setItem(scopedKey('receive-draft'), JSON.stringify(draft))
  } catch {
    // приватный режим/квота — черновик просто не переживёт переход, не критично
  }
}

export function clearReceiveDraft(): void {
  try {
    localStorage.removeItem(scopedKey('receive-draft'))
  } catch {
    // ignore
  }
}
