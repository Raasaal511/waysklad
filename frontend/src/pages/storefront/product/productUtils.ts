import type { StorefrontProductDetail, StorefrontVariant } from '../../../entities/storefront/api'
import { formatQuantity } from '../../../shared/lib/format'

/** Цена варианта, если задана, иначе розничная цена товара. */
export function variantPrice(product: StorefrontProductDetail, variant: StorefrontVariant | null | undefined): string {
  if (variant?.price) return variant.price
  return product.retail_price
}

/** Диапазон цен по всем вариантам товара (для строки "от N ₽", если цены различаются). */
export function priceRange(product: StorefrontProductDetail): { min: string; max: string; sameForAll: boolean } {
  if (product.variants.length === 0) {
    return { min: product.retail_price, max: product.retail_price, sameForAll: true }
  }
  const prices = product.variants.map((v) => Number(v.price ?? product.retail_price))
  const min = Math.min(...prices)
  const max = Math.max(...prices)
  return { min: String(min), max: String(max), sameForAll: min === max }
}

interface StockLike {
  in_stock: boolean
  stock_level: 'out' | 'low' | 'in'
  stock_qty: string | null
}

/** Текст остатка: точное число, если разрешено бэком, иначе по уровню запаса. */
export function stockText(item: StockLike, unitLabel: string): string {
  if (item.stock_qty != null) {
    return `Осталось ${formatQuantity(item.stock_qty)} ${unitLabel}`
  }
  if (item.stock_level === 'out' || !item.in_stock) return 'Нет в наличии'
  if (item.stock_level === 'low') return 'Мало'
  return 'В наличии'
}

const DAY_MS = 24 * 60 * 60 * 1000

const MONTHS_GENITIVE = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
]

/** «сегодня», «вчера», «N дней назад», «N недель назад», иначе «16 сентября 2025». */
export function relativeDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
  const diffDays = Math.round((startOfToday - startOfDate) / DAY_MS)

  if (diffDays === 0) return 'сегодня'
  if (diffDays === 1) return 'вчера'
  if (diffDays > 1 && diffDays < 7) return `${diffDays} ${dayWord(diffDays)} назад`
  if (diffDays >= 7 && diffDays < 30) {
    const weeks = Math.floor(diffDays / 7)
    return `${weeks} ${weekWord(weeks)} назад`
  }
  return `${date.getDate()} ${MONTHS_GENITIVE[date.getMonth()]} ${date.getFullYear()}`
}

function dayWord(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'день'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'дня'
  return 'дней'
}

function weekWord(n: number): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'неделю'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'недели'
  return 'недель'
}

/** Месяц-год в родительном падеже: "сентября 2024" — для "На ВайСклад с …". */
export function formatMonthYearGenitive(iso: string | null | undefined): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return `${MONTHS_GENITIVE[date.getMonth()]} ${date.getFullYear()}`
}

/** Источник фото для галереи: фото товара + storefront_photos, без дублей. */
export function galleryFor(product: StorefrontProductDetail): string[] {
  const list: string[] = []
  if (product.photo) list.push(product.photo)
  for (const p of product.storefront_photos) {
    if (!list.includes(p)) list.push(p)
  }
  return list
}

/** Фото для конкретного варианта, если оно есть — иначе общая галерея товара. */
export function galleryForVariant(product: StorefrontProductDetail, variant: StorefrontVariant | null | undefined): string[] {
  if (variant?.photo) {
    const list = [variant.photo]
    for (const p of galleryFor(product)) {
      if (!list.includes(p)) list.push(p)
    }
    return list
  }
  return galleryFor(product)
}
