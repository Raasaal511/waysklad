const LAST_STORE_KEY = 'waysklad:last-store-slug'

/** Последний открытый магазин — для редиректов со старых /favorites, /cart, /account. */
export function loadLastStoreSlug(): string | null {
  try {
    return localStorage.getItem(LAST_STORE_KEY)
  } catch {
    return null
  }
}

export function saveLastStoreSlug(slug: string) {
  if (!slug) return
  try {
    localStorage.setItem(LAST_STORE_KEY, slug)
  } catch {
    /* приватный режим — редиректы со старых ссылок просто уйдут на /login */
  }
}
