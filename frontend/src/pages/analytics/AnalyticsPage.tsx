import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import {
  getDashboard,
  getTopProducts,
  getCategoryProfit,
  getDeadStock,
  getStockValue,
  getRevenueTimeline,
  getPeriodTotals,
  getMissedSales,
  type Dashboard,
  type ProductSales,
  type CategoryProfit,
  type DeadStockItem,
  type StockValue,
  type TimelinePoint,
  type TimelineBucket,
  type PeriodTotals,
  type MissedSaleItem,
} from '../../entities/analytics/api'
import { ApiError } from '../../shared/api/client'
import { formatQuantity, formatMoney } from '../../shared/lib/format'
import { BarChart, type BarChartPoint } from '../../shared/ui/BarChart'
import { PillTabs } from '../../shared/ui/PillTabs'
import {
  IconReportMoney,
  IconTrendingUp,
  IconShoppingCart,
  IconWallet,
  IconTrophy,
  IconChartPie,
  IconChartBar,
  IconPackageOff,
  IconReceipt,
  IconCoinOff,
  IconShoppingBagX,
  IconCircleCheck,
  type Icon as TablerIcon,
} from '@tabler/icons-react'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './AnalyticsPage.module.css'

const TOP_PRODUCTS_COLUMNS = '2fr 1fr 1fr 1fr 1fr'
const CATEGORY_PROFIT_COLUMNS = '1.6fr 1fr 1fr 1fr 1fr'
const DEAD_STOCK_COLUMNS = '2fr 1fr 1fr 1fr'
const MISSED_SALES_COLUMNS = '2fr 1fr 1fr'

/** Компактный пустой блок внутри секции аналитики — не голый серый текст. */
function SectionEmpty({
  icon: Icon,
  title,
  description,
  tone = 'neutral',
}: {
  icon: TablerIcon
  title: string
  description?: string
  tone?: 'neutral' | 'good'
}) {
  return (
    <div className={`${styles.emptyPanel} ${tone === 'good' ? styles.emptyPanelGood : ''}`}>
      <span className={styles.emptyIcon} aria-hidden="true">
        <Icon size={22} stroke={1.7} />
      </span>
      <div className={styles.emptyText}>
        <strong>{title}</strong>
        {description && <p>{description}</p>}
      </div>
    </div>
  )
}

type PeriodKey = 'month' | 'quarter' | 'year'

const PERIOD_FILTER_KEY = 'analytics_period_filter'
const PERIOD_VALUES: PeriodKey[] = ['month', 'quarter', 'year']

const PERIOD_LABELS: Record<PeriodKey, string> = {
  month: 'Месяц',
  quarter: 'Квартал',
  year: 'Год',
}

const PERIOD_BUCKET: Record<PeriodKey, TimelineBucket> = {
  month: 'day',
  quarter: 'week',
  year: 'month',
}

type MetricKey = 'revenue' | 'profit'

const METRIC_OPTIONS: MetricKey[] = ['revenue', 'profit']

const METRIC_LABELS: Record<MetricKey, string> = {
  revenue: 'Выручка',
  profit: 'Прибыль',
}

/** Календарные границы периода, содержащего anchor (не скользящее окно —
 * ровно с 1-го по последнее число месяца/квартала/года). */
function calendarRange(anchor: Date, period: PeriodKey): { from: Date; to: Date } {
  const y = anchor.getFullYear()
  if (period === 'month') {
    const m = anchor.getMonth()
    return { from: new Date(y, m, 1), to: new Date(y, m + 1, 0) }
  }
  if (period === 'quarter') {
    const q = Math.floor(anchor.getMonth() / 3)
    return { from: new Date(y, q * 3, 1), to: new Date(y, q * 3 + 3, 0) }
  }
  return { from: new Date(y, 0, 1), to: new Date(y, 11, 31) }
}

/** Границы предыдущего периода той же длины (для сравнения "было/стало") —
 * предыдущий месяц/квартал/год, а не скользящее окно назад от сегодня. */
function previousCalendarRange(anchor: Date, period: PeriodKey): { from: Date; to: Date } {
  return calendarRange(shiftAnchor(anchor, period, -1), period)
}

function shiftAnchor(anchor: Date, period: PeriodKey, dir: 1 | -1): Date {
  const d = new Date(anchor)
  if (period === 'month') d.setMonth(d.getMonth() + dir)
  else if (period === 'quarter') d.setMonth(d.getMonth() + dir * 3)
  else d.setFullYear(d.getFullYear() + dir)
  return d
}

const QUARTER_LABELS = ['I', 'II', 'III', 'IV']

function formatRangeTitle(anchor: Date, period: PeriodKey): string {
  if (period === 'month') return anchor.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
  if (period === 'quarter') return `${QUARTER_LABELS[Math.floor(anchor.getMonth() / 3)]} квартал ${anchor.getFullYear()}`
  return String(anchor.getFullYear())
}

const BUCKET_HINT: Record<TimelineBucket, string> = {
  day: 'по дням',
  week: 'по неделям (столбец — сумма за 7 дней, дата — понедельник недели)',
  month: 'по месяцам',
}

const MONTH_SHORT = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

/** Календарная дата в YYYY-MM-DD по локальным компонентам (не toISOString,
 * который конвертирует в UTC и на восточных часовых поясах сдвигает
 * полночь на день назад — "1 августа" превращалось в "31 июля"). */
function toISODate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function formatBucketLabel(iso: string, bucket: TimelineBucket): string {
  const d = parseISODate(iso)
  if (bucket === 'month') return MONTH_SHORT[d.getMonth()]
  if (bucket === 'week') {
    const end = new Date(d)
    end.setDate(end.getDate() + 6)
    const sameMonth = d.getMonth() === end.getMonth()
    return sameMonth
      ? `${d.getDate()}–${end.getDate()} ${MONTH_SHORT[d.getMonth()]}`
      : `${d.getDate()} ${MONTH_SHORT[d.getMonth()]}–${end.getDate()} ${MONTH_SHORT[end.getMonth()]}`
  }
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

/** Компактная подпись для оси, когда точек много (дни месяца) — только
 * число, без месяца, чтобы подпись помещалась под узким столбцом. */
function formatBucketAxis(iso: string, bucket: TimelineBucket): string {
  if (bucket !== 'day') return formatBucketLabel(iso, bucket)
  return String(parseISODate(iso).getDate())
}

function formatBucketFull(iso: string, bucket: TimelineBucket): string {
  const d = parseISODate(iso)
  if (bucket === 'month') return d.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
  if (bucket === 'week') return `Неделя с ${d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}`
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

/** Парсит "YYYY-MM-DD" как локальную календарную дату (не new Date(str),
 * которая трактует такую строку как UTC-полночь и на восточных часовых
 * поясах сдвигает день на -1 при чтении локальными геттерами). */
function parseISODate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function bucketStartOf(d: Date, bucket: TimelineBucket): Date {
  const result = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  if (bucket === 'month') result.setDate(1)
  if (bucket === 'week') {
    const day = result.getDay()
    const diff = (day + 6) % 7 // понедельник — начало недели
    result.setDate(result.getDate() - diff)
  }
  return result
}

function bucketAdd(d: Date, bucket: TimelineBucket): Date {
  const result = new Date(d)
  if (bucket === 'month') result.setMonth(result.getMonth() + 1)
  else if (bucket === 'week') result.setDate(result.getDate() + 7)
  else result.setDate(result.getDate() + 1)
  return result
}

/** Бэкенд отдаёт только бакеты с продажами — пропуски (месяцы/недели/дни без
 * продаж) нужно дозаполнить нулями сами, иначе при малом числе точек график
 * рисует один-два «повисших» бара без временного контекста вместо шкалы. */
function fillTimelineGaps(
  timeline: TimelinePoint[],
  dateFrom: string,
  dateTo: string,
  bucket: TimelineBucket,
): TimelinePoint[] {
  const byBucket = new Map(timeline.map((p) => [p.bucket_start, p]))
  const start = bucketStartOf(parseISODate(dateFrom), bucket)
  const end = bucketStartOf(parseISODate(dateTo), bucket)
  const result: TimelinePoint[] = []
  for (let cursor = start; cursor <= end; cursor = bucketAdd(cursor, bucket)) {
    const key = toISODate(cursor)
    result.push(byBucket.get(key) ?? { bucket_start: key, sales_count: 0, revenue: '0', profit: '0' })
  }
  return result
}

/** Подпись оси значений: колонка 52px — без «₽» и с одним знаком только когда
 * он что-то меняет («5 млн», «3,8 млн», «750 тыс»); иначе «5.0 мл…». */
function formatAxisMoney(value: number): string {
  const short = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1).replace('.', ','))
  if (Math.abs(value) >= 1_000_000) return `${short(Math.round(value / 100_000) / 10)} млн`
  if (Math.abs(value) >= 1_000) return `${Math.round(value / 1_000)} тыс`
  return String(Math.round(value))
}

function formatMoneyShort(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)} млн ₽`
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(0)} тыс ₽`
  return `${value.toFixed(0)} ₽`
}

/** % изменения к предыдущему периоду. null, если сравнивать не с чем —
 * не было продаж в прошлом периоде (0 → N% выглядело бы как случайные "+∞"). */
function percentDelta(current: number | null, previous: number | null): number | null {
  if (current == null || previous == null || previous === 0) return null
  return ((current - previous) / previous) * 100
}

function DeltaBadge({ value }: { value: number | null }) {
  if (value == null) return null
  const flat = Math.abs(value) < 0.05
  const positive = value > 0
  return (
    <span
      className={[styles.heroDelta, flat ? styles.heroDeltaFlat : positive ? styles.heroDeltaUp : styles.heroDeltaDown]
        .filter(Boolean)
        .join(' ')}
    >
      {flat ? '' : positive ? '↑' : '↓'} {Math.abs(value).toFixed(1)}%
    </span>
  )
}

export function AnalyticsPage() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [topProducts, setTopProducts] = useState<ProductSales[]>([])
  const [categoryProfit, setCategoryProfit] = useState<CategoryProfit[]>([])
  const [deadStock, setDeadStock] = useState<DeadStockItem[]>([])
  const [stockValue, setStockValue] = useState<StockValue | null>(null)
  const [timeline, setTimeline] = useState<TimelinePoint[]>([])
  const [prevTotals, setPrevTotals] = useState<PeriodTotals | null>(null)
  const [periodTotals, setPeriodTotals] = useState<PeriodTotals | null>(null)
  const [missedSales, setMissedSales] = useState<MissedSaleItem[]>([])
  // Предпочтение устройства, не аккаунта — переживает обновление страницы.
  const [period, setPeriod] = useState<PeriodKey>(() => {
    const saved = localStorage.getItem(PERIOD_FILTER_KEY)
    return saved && (PERIOD_VALUES as string[]).includes(saved) ? (saved as PeriodKey) : 'year'
  })

  useEffect(() => {
    localStorage.setItem(PERIOD_FILTER_KEY, period)
  }, [period])
  const [anchor, setAnchor] = useState(() => new Date())
  const [metric, setMetric] = useState<MetricKey>('revenue')
  const [loading, setLoading] = useState(true)
  const [periodLoading, setPeriodLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const calRange = useMemo(() => calendarRange(anchor, period), [anchor, period])
  const range = useMemo(
    () => ({ dateFrom: toISODate(calRange.from), dateTo: toISODate(calRange.to) }),
    [calRange],
  )
  const prevRange = useMemo(() => {
    const r = previousCalendarRange(anchor, period)
    return { dateFrom: toISODate(r.from), dateTo: toISODate(r.to) }
  }, [anchor, period])
  const isCurrentPeriod = useMemo(() => {
    const today = new Date()
    return calendarRange(today, period).from.getTime() === calRange.from.getTime()
  }, [calRange, period])

  const bucket = PERIOD_BUCKET[period]

  function changePeriod(next: PeriodKey) {
    setPeriod(next)
    setAnchor(new Date())
  }

  useEffect(() => {
    getDashboard()
      .then(setDashboard)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Не удалось загрузить аналитику'))
      .finally(() => setLoading(false))
    getDeadStock()
      .then(setDeadStock)
      .catch(() => {})
    getStockValue()
      .then(setStockValue)
      .catch(() => {})
  }, [])

  useEffect(() => {
    setPeriodLoading(true)
    Promise.all([
      getTopProducts(range),
      getCategoryProfit(range),
      getRevenueTimeline({ ...range, bucket }),
      getPeriodTotals(prevRange),
      getPeriodTotals(range),
      getMissedSales(range),
    ])
      .then(([t, cp, tl, prev, current, missed]) => {
        setTopProducts(t)
        setCategoryProfit(cp)
        setTimeline(tl)
        setPrevTotals(prev)
        setPeriodTotals(current)
        setMissedSales(missed)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Не удалось загрузить аналитику'))
      .finally(() => setPeriodLoading(false))
  }, [range, prevRange, bucket])

  if (loading) return <p className={layoutStyles.textMuted}>Загрузка…</p>
  if (error) return <p className={layoutStyles.error}>{error}</p>
  if (!dashboard) return null

  const periodRevenue = timeline.reduce((sum, p) => sum + Number(p.revenue), 0)
  const periodProfit = timeline.reduce((sum, p) => sum + Number(p.profit), 0)
  const periodSalesCount = timeline.reduce((sum, p) => sum + p.sales_count, 0)
  const margin = periodRevenue > 0 ? (periodProfit / periodRevenue) * 100 : null
  const avgCheck = periodSalesCount > 0 ? periodRevenue / periodSalesCount : null

  const revenueDelta = percentDelta(periodRevenue, prevTotals ? Number(prevTotals.revenue) : null)
  const profitDelta = percentDelta(periodProfit, prevTotals ? Number(prevTotals.profit) : null)
  const salesDelta = percentDelta(periodSalesCount, prevTotals ? prevTotals.sales_count : null)
  const prevAvgCheck =
    prevTotals && prevTotals.sales_count > 0 ? Number(prevTotals.revenue) / prevTotals.sales_count : null
  const avgCheckDelta = percentDelta(avgCheck, prevAvgCheck)

  const filledTimeline = fillTimelineGaps(timeline, range.dateFrom, range.dateTo, bucket)

  const chartPoints: BarChartPoint[] = filledTimeline.map((p) => {
    const value = Number(metric === 'revenue' ? p.revenue : p.profit)
    const revenue = Number(p.revenue)
    const profit = Number(p.profit)
    const bucketMargin = revenue > 0 ? (profit / revenue) * 100 : null
    const avgCheck = p.sales_count > 0 ? revenue / p.sales_count : null
    return {
      label: formatBucketLabel(p.bucket_start, bucket),
      axisLabel: formatBucketAxis(p.bucket_start, bucket),
      value,
      tooltip: (
        <>
          <strong>{formatMoneyShort(value)}</strong>
          <span>{formatBucketLabel(p.bucket_start, bucket)} · {p.sales_count} прод.</span>
        </>
      ),
      detail: (
        <>
          <div className={[styles.detailItem, styles.detailItemHead].join(' ')}>
            <span className={styles.detailLabel}>{formatBucketFull(p.bucket_start, bucket)}</span>
            <span className={styles.detailValue}>{p.sales_count} продаж</span>
          </div>
          <div className={styles.detailDivider} />
          <div className={styles.detailItem}>
            <span className={styles.detailLabel}>Выручка</span>
            <span className={styles.detailValue}>{formatMoney(revenue)} ₽</span>
          </div>
          <div className={styles.detailItem}>
            <span className={styles.detailLabel}>Прибыль</span>
            <span className={styles.detailValue}>
              {formatMoney(profit)} ₽{bucketMargin != null && ` · ${bucketMargin.toFixed(1)}%`}
            </span>
          </div>
          {avgCheck != null && (
            <div className={styles.detailItem}>
              <span className={styles.detailLabel}>Средний чек</span>
              <span className={styles.detailValue}>{formatMoney(Math.round(avgCheck))} ₽</span>
            </div>
          )}
        </>
      ),
    }
  })

  const sortedCategoryProfit = [...categoryProfit].sort((a, b) => Number(b.profit) - Number(a.profit))

  return (
    <div className={layoutStyles.stack}>
      <h2>Аналитика</h2>

      <div className={styles.periodRow}>
        <PillTabs
          value={period}
          options={Object.keys(PERIOD_LABELS) as PeriodKey[]}
          labels={PERIOD_LABELS}
          onChange={changePeriod}
        />
        <div className={styles.periodNav}>
          <button
            type="button"
            className={styles.periodNavBtn}
            onClick={() => setAnchor((a) => shiftAnchor(a, period, -1))}
            aria-label="Предыдущий период"
          >
            ‹
          </button>
          <span className={styles.periodNavTitle}>{formatRangeTitle(anchor, period)}</span>
          <button
            type="button"
            className={styles.periodNavBtn}
            onClick={() => setAnchor((a) => shiftAnchor(a, period, 1))}
            disabled={isCurrentPeriod}
            aria-label="Следующий период"
          >
            ›
          </button>
        </div>
      </div>

      <div className={styles.heroGrid}>
        <div className={styles.heroCard}>
          <span className={styles.heroIcon}>
            <IconShoppingCart size={22} stroke={1.7} />
          </span>
          <div className={styles.heroBody}>
            <span className={styles.heroLabel}>Продаж за период</span>
            <span className={styles.heroValue}>{periodSalesCount}</span>
            <DeltaBadge value={salesDelta} />
          </div>
        </div>
        <div className={styles.heroCard}>
          <span className={styles.heroIcon}>
            <IconWallet size={22} stroke={1.7} />
          </span>
          <div className={styles.heroBody}>
            <span className={styles.heroLabel}>Выручка за период</span>
            <span className={styles.heroValue}>{formatMoney(periodRevenue)} ₽</span>
            <DeltaBadge value={revenueDelta} />
          </div>
        </div>
        <div className={styles.heroCard}>
          <span className={styles.heroIcon}>
            <IconTrendingUp size={22} stroke={1.7} />
          </span>
          <div className={styles.heroBody}>
            <span className={styles.heroLabel}>Прибыль за период</span>
            <span className={styles.heroValue}>{formatMoney(periodProfit)} ₽</span>
            <div className={styles.heroSubRow}>
              {margin != null && <span className={styles.heroSub}>{margin.toFixed(1)}% маржа</span>}
              <DeltaBadge value={profitDelta} />
            </div>
          </div>
        </div>
        <div className={styles.heroCard}>
          <span className={styles.heroIcon}>
            <IconReceipt size={22} stroke={1.7} />
          </span>
          <div className={styles.heroBody}>
            <span className={styles.heroLabel}>Средний чек</span>
            <span className={styles.heroValue}>{avgCheck != null ? `${formatMoney(Math.round(avgCheck))} ₽` : '—'}</span>
            <DeltaBadge value={avgCheckDelta} />
          </div>
        </div>
        {stockValue && (
          <div className={styles.heroCard}>
            <span className={styles.heroIcon}>
              <IconReportMoney size={22} stroke={1.7} />
            </span>
            <div className={styles.heroBody}>
              <span className={styles.heroLabel}>Деньги в товаре</span>
              <span className={styles.heroValue}>{formatMoney(stockValue.total_value)} ₽</span>
            </div>
          </div>
        )}
        {periodTotals && Number(periodTotals.change_kept ?? 0) > 0 && (
          <div className={styles.heroCard}>
            <span className={styles.heroIcon}>
              <IconCoinOff size={22} stroke={1.7} />
            </span>
            <div className={styles.heroBody}>
              <span className={styles.heroLabel}>Невзятая сдача</span>
              <span className={styles.heroValue}>{formatMoney(periodTotals.change_kept ?? 0)} ₽</span>
              <span className={styles.heroSub}>осталась в кассе сверх чека</span>
            </div>
          </div>
        )}
      </div>

      <div className={layoutStyles.stack}>
        <div className={styles.sectionHeadingRow}>
          <div className={styles.sectionHeading}>
            <IconChartBar size={17} stroke={1.8} className={styles.sectionHeadingIcon} />
            <h3>Динамика</h3>
          </div>
          <PillTabs
            className={styles.metricTabs}
            value={metric}
            options={METRIC_OPTIONS}
            labels={METRIC_LABELS}
            onChange={setMetric}
          />
        </div>
        <p className={styles.chartHint}>
          Группировка {BUCKET_HINT[bucket]} · нажмите на столбец, чтобы посмотреть детали
        </p>
        <div className={`${layoutStyles.card} ${layoutStyles.cardFull}`}>
          {periodLoading ? (
            <p className={layoutStyles.textMuted}>Загрузка…</p>
          ) : (
            <BarChart points={chartPoints} formatValue={formatAxisMoney} emptyMessage="Продаж за период нет" />
          )}
        </div>
      </div>

      <div className={layoutStyles.stack}>
        <div className={styles.sectionHeading}>
          <IconTrophy size={17} stroke={1.8} className={styles.sectionHeadingIcon} />
          <h3>Топ товаров за период</h3>
        </div>
        {topProducts.length === 0 ? (
          <SectionEmpty
            icon={IconTrophy}
            title="Пока нет продаж за период"
            description="Когда появятся продажи, здесь будет топ товаров по выручке."
          />
        ) : (
          <div
            className={`${layoutStyles.dataTable} ${layoutStyles.dataTableScroll} ${styles.compactTable}`}
            style={{ gridTemplateColumns: TOP_PRODUCTS_COLUMNS }}
          >
            <div className={layoutStyles.dataTableHead}>
              <span>Товар</span>
              <span>Продано</span>
              <span>Выручка</span>
              <span>Ср. чек</span>
              <span>Доля</span>
            </div>
            <div className={layoutStyles.dataTableBody}>
              {topProducts.map((p, i) => {
                const share = periodRevenue > 0 ? (Number(p.revenue) / periodRevenue) * 100 : null
                const avgPrice = Number(p.quantity_sold) > 0 ? Number(p.revenue) / Number(p.quantity_sold) : null
                return (
                  <div
                    key={p.product_id}
                    className={`${layoutStyles.dataRow} sale-history-row-in`}
                    style={
                      {
                        '--row-delay': `${Math.min(i, 12) * 25}ms`,
                      } as CSSProperties
                    }
                  >
                    <span className={layoutStyles.dataRowName}>{p.product_name}</span>
                    <span>{formatQuantity(p.quantity_sold)}</span>
                    <span>{formatMoney(p.revenue)} ₽</span>
                    <span>{avgPrice != null ? `${formatMoney(Math.round(avgPrice))} ₽` : '—'}</span>
                    <span>{share != null ? `${share.toFixed(1)}%` : '—'}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      <div className={layoutStyles.stack}>
        <div className={styles.sectionHeading}>
          <IconChartPie size={17} stroke={1.8} className={styles.sectionHeadingIcon} />
          <h3>Прибыльность по категориям</h3>
        </div>
        {categoryProfit.length === 0 ? (
          <SectionEmpty
            icon={IconChartPie}
            title="Категорий пока не видно"
            description="Маржа и доля появятся после первых продаж с категориями."
          />
        ) : (
          <div
            className={`${layoutStyles.dataTable} ${layoutStyles.dataTableScroll} ${styles.compactTable}`}
            style={{ gridTemplateColumns: CATEGORY_PROFIT_COLUMNS }}
          >
            <div className={layoutStyles.dataTableHead}>
              <span>Категория</span>
              <span>Выручка</span>
              <span>Прибыль</span>
              <span>Маржа</span>
              <span>Доля</span>
            </div>
            <div className={layoutStyles.dataTableBody}>
              {sortedCategoryProfit.map((c, i) => {
                const catMargin = Number(c.revenue) > 0 ? (Number(c.profit) / Number(c.revenue)) * 100 : null
                const share = periodRevenue > 0 ? (Number(c.revenue) / periodRevenue) * 100 : null
                return (
                  <div
                    key={c.category_id ?? 'none'}
                    className={`${layoutStyles.dataRow} sale-history-row-in`}
                    style={
                      {
                        '--row-delay': `${Math.min(i, 12) * 25}ms`,
                      } as CSSProperties
                    }
                  >
                    <span className={layoutStyles.dataRowName}>{c.category_name}</span>
                    <span>{formatMoney(c.revenue)} ₽</span>
                    <span>{formatMoney(c.profit)} ₽</span>
                    <span className={styles.marginCell}>
                      {catMargin != null ? (
                        <span className={marginBadgeClass(catMargin)}>{catMargin.toFixed(1)}%</span>
                      ) : (
                        '—'
                      )}
                    </span>
                    <span>{share != null ? `${share.toFixed(1)}%` : '—'}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      <div className={layoutStyles.stack}>
        <div className={styles.sectionHeading}>
          <IconPackageOff size={17} stroke={1.8} className={styles.sectionHeadingIcon} />
          <h3>Мёртвый остаток (60+ дней)</h3>
        </div>
        {deadStock.length === 0 ? (
          <SectionEmpty
            icon={IconCircleCheck}
            tone="good"
            title="Залежавшихся товаров нет"
            description="Ничего не лежит без продаж дольше 60 дней — хороший знак."
          />
        ) : (
          <div
            className={`${layoutStyles.dataTable} ${layoutStyles.dataTableScroll} ${styles.compactTable}`}
            style={{ gridTemplateColumns: DEAD_STOCK_COLUMNS }}
          >
            <div className={layoutStyles.dataTableHead}>
              <span>Товар</span>
              <span>Остаток</span>
              <span>Заморожено</span>
              <span>Без продаж</span>
            </div>
            <div className={layoutStyles.dataTableBody}>
              {deadStock.map((d, i) => {
                const frozenValue = Number(d.quantity) * Number(d.purchase_price)
                const daysSinceSale = d.last_sale_at
                  ? Math.floor((Date.now() - new Date(d.last_sale_at).getTime()) / 86_400_000)
                  : null
                return (
                  <div
                    key={d.product_id}
                    className={`${layoutStyles.dataRow} sale-history-row-in`}
                    style={
                      {
                        '--row-delay': `${Math.min(i, 12) * 25}ms`,
                      } as CSSProperties
                    }
                  >
                    <span className={layoutStyles.dataRowName}>{d.product_name}</span>
                    <span>{formatQuantity(d.quantity)}</span>
                    <span>{formatMoney(frozenValue)} ₽</span>
                    <span className={layoutStyles.textMuted}>
                      {daysSinceSale != null ? `${daysSinceSale} дн.` : 'никогда'}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      <div className={layoutStyles.stack}>
        <div className={styles.sectionHeading}>
          <IconShoppingBagX size={17} stroke={1.8} className={styles.sectionHeadingIcon} />
          <h3>Упущенные продажи с витрины</h3>
        </div>
        <p className={styles.chartHint}>
          Заявки, где покупатель просил товар, а остатка не хватило
        </p>
        {missedSales.length === 0 ? (
          <SectionEmpty
            icon={IconCircleCheck}
            tone="good"
            title="Упущенных заявок нет"
            description="За период покупатели не просили то, чего не было на остатке."
          />
        ) : (
          <div
            className={`${layoutStyles.dataTable} ${layoutStyles.dataTableScroll} ${styles.compactTable}`}
            style={{ gridTemplateColumns: MISSED_SALES_COLUMNS }}
          >
            <div className={layoutStyles.dataTableHead}>
              <span>Товар</span>
              <span>Заявок</span>
              <span>Просили</span>
            </div>
            <div className={layoutStyles.dataTableBody}>
              {missedSales.map((m, i) => (
                <div
                  key={m.product_id}
                  className={`${layoutStyles.dataRow} sale-history-row-in`}
                  style={
                    {
                      '--row-delay': `${Math.min(i, 12) * 25}ms`,
                    } as CSSProperties
                  }
                >
                  <span className={layoutStyles.dataRowName}>{m.product_name}</span>
                  <span>{m.requests_count}</span>
                  <span>{formatQuantity(m.quantity_requested)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function marginBadgeClass(margin: number): string {
  if (margin < 15) return 'badge pill danger'
  if (margin < 30) return 'badge pill warning'
  return 'badge pill accent'
}
