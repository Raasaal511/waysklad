/**
 * Избранное покупателя. У покупателя нет единого аккаунта на все магазины,
 * поэтому список id хранится в localStorage отдельным ключом на каждый магазин
 * (waysklad:storefront-favorites:<slug>) — так же, как корзина (pages/storefront/cart.ts).
 *
 * Страница /favorites собирает избранное по всем магазинам сразу, поэтому вся
 * работа с ключами живёт здесь, а не внутри страницы каталога.
 */
export const FAVORITES_PREFIX = 'waysklad:storefront-favorites:'

/** Событие «избранное изменилось» — как 'waysklad:storefront-cart' у корзины.
 *  Шапка и страница избранного подписаны на него, чтобы счётчик обновлялся
 *  мгновенно, без ожидания смены роута. */
export const FAVORITES_EVENT = 'waysklad:storefront-favorites'

export interface FavoritesEntry {
  slug: string
  ids: number[]
}

function parseIds(raw: string | null): number[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter((id): id is number => typeof id === 'number')
  } catch {
    // повреждённая запись — считаем, что избранного нет, а не валим экран
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
      // пустой список не храним — иначе в localStorage копятся ключи магазинов,
      // из которых покупатель всё убрал, и страница /favorites ходит за ними зря
      localStorage.removeItem(`${FAVORITES_PREFIX}${slug}`)
    }
  } catch {
    // приватный режим / переполненное хранилище — интерфейс продолжает работать
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

/** Избранное по всем магазинам сразу — источник данных страницы /favorites. */
export function loadAllFavorites(): FavoritesEntry[] {
  const entries: FavoritesEntry[] = []
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (!key || !key.startsWith(FAVORITES_PREFIX)) continue
      const slug = key.slice(FAVORITES_PREFIX.length)
      if (!slug) continue
      const ids = parseIds(localStorage.getItem(key))
      if (ids.length > 0) entries.push({ slug, ids })
    }
  } catch {
    // localStorage недоступен — считаем, что избранного нет
    return []
  }
  return entries
}
