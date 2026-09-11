const quantityFormatter = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 3,
})

/** Остатки на бэкенде хранятся как Decimal(14,3): "12.000" для штук, "1.500" для кг и т.п. */
export function formatQuantity(value: string | number): string {
  const num = Number(value)
  if (!Number.isFinite(num)) return String(value)
  return quantityFormatter.format(num).replace(/\u00A0/g, '\u202F')
}

const moneyFormatter = new Intl.NumberFormat('ru-RU', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})

/* Суммы: фиксируем минимум 2 знака только если есть копейки; разрядность через тонкий пробел уже даёт ru-RU.
   Дополнительно нормализуем узкий неразрывный пробел для стабильного вида. */
export function formatMoney(value: string | number): string {
  const num = Number(value)
  if (!Number.isFinite(num)) return String(value)
  return moneyFormatter.format(num).replace(/\u00A0/g, '\u202F')
}

/**
 * Сумма строки чека в копейках (целое число), чтобы избежать накопления
 * ошибки округления float при суммировании дробных количеств (кг, л, м...).
 * Итоговая сумма чека должна складываться из этих округлённых построчных сумм,
 * а не из сырых произведений quantity*price — иначе отображаемый subtotal
 * может разойтись с суммой отображаемых строк на копейку.
 */
export function lineTotalCents(quantity: string | number, price: string | number): number {
  const qty = Number(quantity || 0)
  const p = Number(price || 0)
  if (!Number.isFinite(qty) || !Number.isFinite(p)) return 0
  return Math.round(qty * p * 100)
}

export function centsToMoney(cents: number): number {
  return cents / 100
}

/**
 * Нормализует ввод дробного числа: запятая → точка (на lang="ru" браузеры
 * по-разному трактуют разделитель в type="number", поэтому такие поля лучше
 * делать type="text" inputMode="decimal" и нормализовать вручную).
 * Возвращает null, если ввод не является допустимым префиксом числа
 * (сохраняет промежуточные состояния вроде "12," при наборе).
 */
export function normalizeDecimalInput(rawValue: string): string | null {
  const value = rawValue.replace(',', '.')
  if (value !== '' && !/^\d*\.?\d*$/.test(value)) return null
  return value
}

/** Остаток закончился — товара нет вообще. */
export function isOutOfStock(quantity: string | number): boolean {
  return Number(quantity) <= 0
}

/**
 * Остаток мало (задан min_stock > 0 и текущий остаток его не превышает), но товар
 * ещё есть в наличии (> 0) — это не «закончилось», а просто «пора закупить».
 */
export function isLowStock(quantity: string | number, minStock: string | number): boolean {
  const qty = Number(quantity)
  const min = Number(minStock)
  return qty > 0 && min > 0 && qty <= min
}

/** Склонение "продажа/продажи/продаж" по числу. */
export function pluralizeSales(count: number): string {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return 'продажа'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'продажи'
  return 'продаж'
}

/** Склонение "товар/товара/товаров" по числу. */
export function pluralizeGoods(count: number): string {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return 'товару'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'товарам'
  return 'товарам'
}
