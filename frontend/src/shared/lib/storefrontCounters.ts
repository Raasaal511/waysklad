import { cartCount, type StorefrontCartItem } from '../../pages/storefront/cart'
import { FAVORITES_PREFIX } from './favorites'

/**
 * Избранное и корзина хранятся в localStorage отдельным ключом на каждый
 * магазин (waysklad:storefront-favorites:<slug>, waysklad:storefront-cart:<slug>) —
 * у покупателя нет единого аккаунта на все магазины. Общая шапка (PublicHeader)
 * показывает один счётчик на весь сайт, поэтому здесь считаем сумму по всем
 * ключам такого вида, а не по одному конкретному магазину.
 */
const CART_PREFIX = 'waysklad:storefront-cart:'

function sumAcrossKeys(prefix: string, countFor: (raw: string) => number): number {
  let total = 0
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (!key || !key.startsWith(prefix)) continue
      const raw = localStorage.getItem(key)
      if (!raw) continue
      try {
        total += countFor(raw)
      } catch {
        // повреждённая запись — пропускаем, не валим счётчик всей шапки
      }
    }
  } catch {
    // localStorage недоступен (приватный режим) — счётчик просто нулевой
    return 0
  }
  return total
}

export function totalFavoritesCount(): number {
  return sumAcrossKeys(FAVORITES_PREFIX, (raw) => {
    const ids = JSON.parse(raw) as number[]
    return Array.isArray(ids) ? ids.length : 0
  })
}

export function totalCartCount(): number {
  return sumAcrossKeys(CART_PREFIX, (raw) => {
    const items = JSON.parse(raw) as StorefrontCartItem[]
    return Array.isArray(items) ? cartCount(items) : 0
  })
}
