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
 * \u0426\u0435\u043D\u0430 \u0442\u043E\u0432\u0430\u0440\u0430 \u0434\u043B\u044F \u0432\u0438\u0442\u0440\u0438\u043D\u044B: 0 \u20BD \u043D\u0430 \u043F\u0440\u0430\u043A\u0442\u0438\u043A\u0435 \u0437\u043D\u0430\u0447\u0438\u0442 \u00AB\u0446\u0435\u043D\u0443 \u043D\u0435 \u0437\u0430\u043F\u043E\u043B\u043D\u0438\u043B\u0438\u00BB, \u0430 \u043D\u0435 \u00AB\u0431\u0435\u0441\u043F\u043B\u0430\u0442\u043D\u043E\u00BB \u2014
 * \u044D\u0442\u043E \u043E\u043F\u0442-\u043A\u0430\u0442\u0430\u043B\u043E\u0433, \u043D\u0435 \u043F\u0440\u043E\u043C\u043E-\u0440\u0430\u0437\u0434\u0430\u0447\u0430. \u041F\u043E\u043A\u0430\u0437\u044B\u0432\u0430\u0435\u043C \u00AB\u0426\u0435\u043D\u0430 \u043F\u043E \u0437\u0430\u043F\u0440\u043E\u0441\u0443\u00BB, \u0430 \u043D\u0435 \u0432\u0432\u043E\u0434\u044F\u0449\u0438\u0439 \u0432
 * \u0437\u0430\u0431\u043B\u0443\u0436\u0434\u0435\u043D\u0438\u0435 \u00AB0 \u20BD\u00BB (\u043F\u0440\u0430\u0432\u0438\u043B\u043E \u00AB\u043D\u0438\u0447\u0435\u0433\u043E \u043D\u0435 \u043E\u0431\u0435\u0449\u0430\u0435\u043C \u0442\u043E\u0433\u043E, \u0447\u0435\u0433\u043E \u043D\u0435 \u0434\u0435\u043B\u0430\u0435\u043C\u00BB, \u0441\u043C.
 * docs/UX_SIMPLICITY_RULES.md). \u041F\u0440\u0438\u043C\u0435\u043D\u044F\u0435\u0442\u0441\u044F \u043E\u0434\u0438\u043D\u0430\u043A\u043E\u0432\u043E \u0432 ProductCard, ProductHeader \u0438 TotalCard.
 */
export function formatPriceOrRequest(value: string | number): string {
  const num = Number(value)
  if (Number.isFinite(num) && num <= 0) return '\u0426\u0435\u043D\u0430 \u043F\u043E \u0437\u0430\u043F\u0440\u043E\u0441\u0443'
  return `${formatMoney(value)} \u20BD`
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

/**
 * Общее склонение по числу для трёх форм ["отзыв", "отзыва", "отзывов"].
 * forms[0] — 1, forms[1] — 2..4, forms[2] — 5..20 и остальные.
 */
export function plural(count: number, forms: [string, string, string]): string {
  const n = Math.abs(Math.trunc(count))
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return forms[0]
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return forms[1]
  return forms[2]
}

/** Разряды тонким пробелом: 1 234 567. Для счётчиков, не для денег (см. formatMoney). */
export function formatCount(value: number): string {
  return new Intl.NumberFormat('ru-RU').format(value).replace(/ /g, ' ')
}

const BYTE_UNITS = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']

/** Размер файла или памяти: 1.5 ГБ. null → «нет данных» решает вызывающий. */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
    value /= 1024
    unit += 1
  }
  // байты и килобайты дробными показывать незачем
  const digits = unit < 2 ? 0 : value < 10 ? 1 : 0
  return `${value.toFixed(digits).replace('.', ',')} ${BYTE_UNITS[unit]}`
}

const MINUTE = 60
const HOUR = MINUTE * 60
const DAY = HOUR * 24

/**
 * «2 часа назад», «5 дней назад» — одна функция на весь проект, чтобы
 * одинаковый промежуток везде назывался одинаково. Точную дату показывает
 * вызывающий (обычно в title), здесь только относительная форма.
 */
export function formatRelativeTime(value: string | Date | null | undefined): string {
  if (!value) return 'никогда'
  const date = typeof value === 'string' ? new Date(value) : value
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000)
  if (!Number.isFinite(seconds)) return '—'
  if (seconds < 0) return 'только что'
  if (seconds < MINUTE) return 'только что'
  if (seconds < HOUR) {
    const minutes = Math.floor(seconds / MINUTE)
    return `${minutes} ${plural(minutes, ['минуту', 'минуты', 'минут'])} назад`
  }
  if (seconds < DAY) {
    const hours = Math.floor(seconds / HOUR)
    return `${hours} ${plural(hours, ['час', 'часа', 'часов'])} назад`
  }
  const days = Math.floor(seconds / DAY)
  if (days < 30) return `${days} ${plural(days, ['день', 'дня', 'дней'])} назад`
  const months = Math.floor(days / 30)
  if (months < 12) return `${months} ${plural(months, ['месяц', 'месяца', 'месяцев'])} назад`
  const years = Math.floor(days / 365)
  return `${years} ${plural(years, ['год', 'года', 'лет'])} назад`
}

/** Полная дата и время для тултипа рядом с относительным временем. */
export function formatExactDateTime(value: string | Date | null | undefined): string {
  if (!value) return ''
  const date = typeof value === 'string' ? new Date(value) : value
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
