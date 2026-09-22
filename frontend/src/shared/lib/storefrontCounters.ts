import { cartCount, loadCart, type StorefrontCartItem } from '../../pages/storefront/cart'
import { FAVORITES_PREFIX, loadFavorites } from './favorites'

/**
 * Избранное и корзина — ключ на магазин
 * (waysklad:storefront-favorites:<slug>, waysklad:storefront-cart:<slug>).
 * В шапке магазина считаем только текущий slug.
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
        // повреждённая запись — пропускаем
      }
    }
  } catch {
    return 0
  }
  return total
}

/** Сумма по всем магазинам — только для редких случаев вне контекста магазина. */
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

export function favoritesCountForSlug(slug: string): number {
  return loadFavorites(slug).length
}

export function cartCountForSlug(slug: string): number {
  return cartCount(loadCart(slug))
}
