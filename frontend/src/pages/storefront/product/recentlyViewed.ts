const KEY_PREFIX = 'waysklad:recent:'
const MAX_ITEMS = 20

export interface RecentProduct {
  id: number
  name: string
  retail_price: string
  photo: string
  in_stock: boolean
}

function key(slug: string) {
  return `${KEY_PREFIX}${slug}`
}

export function loadRecentlyViewed(slug: string): RecentProduct[] {
  try {
    const raw = localStorage.getItem(key(slug))
    return raw ? (JSON.parse(raw) as RecentProduct[]) : []
  } catch {
    return []
  }
}

/** Добавляет товар в начало списка «Вы недавно смотрели», без дублей, максимум MAX_ITEMS. */
export function pushRecentlyViewed(slug: string, product: RecentProduct) {
  try {
    const list = loadRecentlyViewed(slug).filter((p) => p.id !== product.id)
    list.unshift(product)
    localStorage.setItem(key(slug), JSON.stringify(list.slice(0, MAX_ITEMS)))
  } catch {
    // localStorage недоступен (приватный режим и т.п.) — тихо игнорируем
  }
}
