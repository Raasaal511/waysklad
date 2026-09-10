import { scopedKey } from '../../shared/lib/scopedStorage'
import type { Product } from '../../entities/product/api'
import type { PaymentMethod } from '../../entities/sale/api'

export interface CartLine {
  product: Product
  quantity: string
  price: string
}

export interface SaleDraft {
  warehouseId: number | null
  cart: CartLine[]
  payment: PaymentMethod
  discount: string
  discountMode: 'amount' | 'percent'
  clientId: number | null
}

export function loadDraft(): SaleDraft | null {
  try {
    const raw = localStorage.getItem(scopedKey('sale-draft'))
    return raw ? (JSON.parse(raw) as SaleDraft) : null
  } catch {
    return null
  }
}

export function saveDraft(draft: SaleDraft) {
  try {
    localStorage.setItem(scopedKey('sale-draft'), JSON.stringify(draft))
  } catch {
    // localStorage недоступен (приватный режим и т.п.) — черновик просто не переживёт перезагрузку
  }
}

export function clearDraft() {
  localStorage.removeItem(scopedKey('sale-draft'))
}

export const PAYMENT_LABELS: Record<PaymentMethod, string> = {
  cash: 'Наличные',
  transfer: 'Перевод',
  credit: 'В долг',
}

export const PAYMENT_BADGE_CLASS: Record<PaymentMethod, string> = {
  cash: 'badge accent',
  transfer: 'badge',
  credit: 'badge danger',
}
