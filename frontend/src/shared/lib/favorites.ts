/**
 * Избранное покупателя по магазину.
 * Ключ: waysklad:storefront-favorites:<slug> — как корзина (pages/storefront/cart.ts).
 * Страница /store/:slug/favorites читает только свой slug.
 */
export const FAVORITES_PREFIX = 'waysklad:storefront-favorites:'

/** Событие «избранное изменилось» — счётчик в шапке и нижняя навигация. */
export const FAVORITES_EVENT = 'waysklad:storefront-favorites'

function parseIds(raw: string | null): number[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter((id): id is number => typeof id === 'number')
  } catch {
    return []
  }
}

export function loadFavorites(slug: string): number[] {
  try {
    return parseIds(localStorage.getItem(`${FAVORITES_PREFIX}${slug}`))
  } catch {
    return []
  }
}

export function saveFavorites(slug: string, ids: number[]) {
  try {
    if (ids.length > 0) {
      localStorage.setItem(`${FAVORITES_PREFIX}${slug}`, JSON.stringify(ids))
    } else {
      localStorage.removeItem(`${FAVORITES_PREFIX}${slug}`)
    }
  } catch {
    // приватный режим / переполненное хранилище
  }
  notifyFavoritesChanged()
}

export function notifyFavoritesChanged() {
  window.dispatchEvent(new Event(FAVORITES_EVENT))
}

/** Переключает товар в избранном и возвращает новый список магазина. */
export function toggleFavorite(slug: string, productId: number): number[] {
  const prev = loadFavorites(slug)
  const next = prev.includes(productId)
    ? prev.filter((id) => id !== productId)
    : [...prev, productId]
  saveFavorites(slug, next)
  return next
}

export function addFavorite(slug: string, productId: number) {
  const prev = loadFavorites(slug)
  if (prev.includes(productId)) return
  saveFavorites(slug, [...prev, productId])
}

export function removeFavorite(slug: string, productId: number) {
  const prev = loadFavorites(slug)
  if (!prev.includes(productId)) return
  saveFavorites(
    slug,
    prev.filter((id) => id !== productId),
  )
}
