import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { listProducts, type Product } from '../../entities/product/api'
import { searchClients, type Client } from '../../entities/counterparty/api'
import { useCatalog } from '../../app/CatalogContext'
import {
  listSales,
  getSalesSummary,
  type PaymentMethod,
  type Sale,
  type SalesSummary,
} from '../../entities/sale/api'
import {
  IconPlus,
  IconBuildingWarehouse,
  IconUsers,
} from '@tabler/icons-react'
import { ApiError } from '../../shared/api/client'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { EmptyState } from '../../shared/ui/EmptyState'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
import { ResetFiltersButton } from '../../shared/ui/ResetFiltersButton'
import { PillTabs } from '../../shared/ui/PillTabs'
import { useAnimatedNumber } from '../../shared/lib/useAnimatedNumber'
import {
  formatMoney,
  pluralizeSales,
} from '../../shared/lib/format'
import { loadDraft, PAYMENT_LABELS, PAYMENT_BADGE_CLASS } from './saleDraft'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './SalePage.module.css'

const PAGE_SIZE = 50

type PeriodFilter = 'today' | 'week' | 'month' | 'all'

const PERIOD_FILTER_KEY = 'sales_period_filter'
const PERIOD_VALUES: PeriodFilter[] = ['today', 'week', 'month', 'all']

const PERIOD_LABELS: Record<PeriodFilter, string> = {
  all: 'Всё',
  month: 'Месяц',
  week: 'Неделя',
  today: 'День',
}

type SaleSortMode = 'date_desc' | 'date_asc' | 'payment'

const SALE_SORT_LABELS: Record<SaleSortMode, string> = {
  date_desc: 'Сначала новые',
  date_asc: 'Сначала старые',
  payment: 'По способу оплаты',
}

function toISODate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function periodToDateRange(period: PeriodFilter): { from: string | null; to: string | null } {
  if (period === 'all') return { from: null, to: null }
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  if (period === 'today') return { from: toISODate(startOfToday), to: null }
  if (period === 'week') {
    const weekAgo = new Date(startOfToday)
    weekAgo.setDate(weekAgo.getDate() - 6)
    return { from: toISODate(weekAgo), to: null }
  }
  const monthAgo = new Date(startOfToday)
  monthAgo.setDate(monthAgo.getDate() - 29)
  return { from: toISODate(monthAgo), to: null }
}

function dayLabel(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  const diffDays = Math.round((startOfToday.getTime() - startOfDate.getTime()) / 86400000)
  if (diffDays === 0) return 'Сегодня'
  if (diffDays === 1) return 'Вчера'
  return startOfDate.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', weekday: 'short' })
}

export function SalePage() {
  const { warehouses, ensureWarehouses } = useCatalog()
  const [sales, setSales] = useState<Sale[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [hasDraft] = useState(() => loadDraft() !== null)

  // Старые deep links /?open=1 и /?openSale=id → dedicated routes
  useEffect(() => {
    if (searchParams.get('open') === '1') {
      navigate('/sales/new', { replace: true })
      return
    }
    const openSaleId = searchParams.get('openSale')
    if (openSaleId) {
      navigate(`/sales/${openSaleId}`, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  // Выбор периода (День/Неделя/Месяц/Всё) — предпочтение устройства, не аккаунта
  // (как тема/вид доски), переживает обновление страницы.
  const [period, setPeriod] = useState<PeriodFilter>(() => {
    const saved = localStorage.getItem(PERIOD_FILTER_KEY)
    return saved && (PERIOD_VALUES as string[]).includes(saved) ? (saved as PeriodFilter) : 'all'
  })

  useEffect(() => {
    localStorage.setItem(PERIOD_FILTER_KEY, period)
  }, [period])
  const [specificDateFrom, setSpecificDateFrom] = useState('')
  const [specificDateTo, setSpecificDateTo] = useState('')
  const [paymentFilter, setPaymentFilter] = useState<PaymentMethod | 'all'>('all')
  const [warehouseFilter, setWarehouseFilter] = useState<number | 'all'>('all')
  const [clientQuery, setClientQuery] = useState('')
  const [debouncedClientQuery, setDebouncedClientQuery] = useState('')
  const [productFilter, setProductFilter] = useState<{ id: number; name: string } | null>(null)
  const [sortMode, setSortMode] = useState<SaleSortMode>('date_desc')
  const [pinned, setPinned] = useState(false)
  const [total, setTotal] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [summary, setSummary] = useState<SalesSummary | null>(null)
  const sentinelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return
    const observer = new IntersectionObserver(([entry]) => setPinned(!entry.isIntersecting), {
      threshold: 0,
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedClientQuery(clientQuery), 300)
    return () => clearTimeout(timer)
  }, [clientQuery])

  const dateRange = useMemo(
    () => (specificDateFrom ? { from: specificDateFrom, to: specificDateTo || specificDateFrom } : periodToDateRange(period)),
    [period, specificDateFrom, specificDateTo],
  )

async function loadSalesPage(params: {
    warehouseFilter: number | 'all'
    paymentFilter: PaymentMethod | 'all'
    productId: number | null
    dateRange: { from: string | null; to: string | null }
    sortMode: SaleSortMode
    offset?: number
  }) {
    return listSales({
      limit: PAGE_SIZE,
      offset: params.offset ?? 0,
      warehouseId: params.warehouseFilter === 'all' ? null : params.warehouseFilter,
      paymentMethod: params.paymentFilter,
      productId: params.productId,
      dateFrom: params.dateRange.from,
      dateTo: params.dateRange.to,
      sort: params.sortMode,
    })
  }

  // Первая загрузка страницы — показывает полноэкранный "Загрузка…" и тянет
  // клиентов/склады заодно. Смена фильтра ими не пользуется — см. reloadSales.
  async function load() {
    setLoading(true)
    try {
      const [{ items, total: t }, , c] = await Promise.all([
        loadSalesPage({ warehouseFilter, paymentFilter, productId: productFilter?.id ?? null, dateRange, sortMode }),
        ensureWarehouses(),
        searchClients(),
      ])
      setSales(items)
      setTotal(t)
      setClients(c)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить продажи')
    } finally {
      setLoading(false)
    }
  }

  const isFirstLoad = useRef(true)

  // Перезагрузка списка при смене фильтра — без полноэкранного "Загрузка…" и
  // без повторных запросов клиентов/складов (они не зависят от фильтра продаж).
  async function reloadSales() {
    try {
      const { items, total: t } = await loadSalesPage({
        warehouseFilter, paymentFilter, productId: productFilter?.id ?? null, dateRange, sortMode,
      })
      setSales(items)
      setTotal(t)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить продажи')
    }
  }

  async function loadMore() {
    setLoadingMore(true)
    try {
      const { items, total: t } = await loadSalesPage({
        warehouseFilter, paymentFilter, productId: productFilter?.id ?? null, dateRange, sortMode,
        offset: sales.length,
      })
      setSales((prev) => [...prev, ...items])
      setTotal(t)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить продажи')
    } finally {
      setLoadingMore(false)
    }
  }

  useEffect(() => {
    if (isFirstLoad.current) {
      isFirstLoad.current = false
      load()
    } else {
      reloadSales()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [warehouseFilter, paymentFilter, productFilter?.id, sortMode, dateRange.from, dateRange.to])

  useEffect(() => {
    getSalesSummary({
      warehouseId: warehouseFilter === 'all' ? null : warehouseFilter,
      dateFrom: dateRange.from,
      dateTo: dateRange.to,
    })
      .then(setSummary)
      .catch(() => {})
  }, [warehouseFilter, dateRange.from, dateRange.to])

  const warehouseName = (id: number) => warehouses.find((w) => w.id === id)?.name ?? `#${id}`
  const clientName = (id: number | null) =>
    id == null ? null : clients.find((c) => c.id === id)?.name ?? `#${id}`

  // Текстовый поиск по клиенту остаётся клиентским: имя не хранится в продаже
  // (только client_id), а полноценный серверный поиск по подстроке имени
  // потребовал бы JOIN ради второстепенного фильтра — фильтруем уже
  // загруженную (сервером отфильтрованную по остальным критериям) страницу.
  const filteredSales = useMemo(() => {
    const query = debouncedClientQuery.trim().toLowerCase()
    if (!query) return sales
    return sales.filter((s) => (clientName(s.client_id) ?? '').toLowerCase().includes(query))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sales, debouncedClientQuery, clients])

  const groups = useMemo(() => {
    if (sortMode === 'payment') {
      const map = new Map<PaymentMethod, Sale[]>()
      for (const s of filteredSales) {
        if (!map.has(s.payment_method)) map.set(s.payment_method, [])
        map.get(s.payment_method)!.push(s)
      }
      return Array.from(map.entries()).map(([method, list]) => ({
        label: PAYMENT_LABELS[method],
        total: list.reduce((sum, s) => sum + Number(s.total), 0),
        count: list.length,
        sales: list,
      }))
    }
    const map = new Map<string, Sale[]>()
    for (const s of filteredSales) {
      const key = new Date(s.created_at).toDateString()
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(s)
    }
    return Array.from(map.entries()).map(([, list]) => ({
      label: dayLabel(list[0].created_at),
      total: list.reduce((sum, s) => sum + Number(s.total), 0),
      count: list.length,
      sales: list,
    }))
  }, [filteredSales, sortMode])

  const periodTotal = filteredSales.reduce((sum, s) => sum + Number(s.total), 0)
  const avgCheck = filteredSales.length > 0 ? periodTotal / filteredSales.length : 0
  const animatedPeriodTotal = useAnimatedNumber(periodTotal)
  const animatedSalesCount = useAnimatedNumber(filteredSales.length)
  const animatedAvgCheck = useAnimatedNumber(avgCheck)
  const paymentStats: Record<PaymentMethod, { total: number; count: number }> = {
    cash: { total: 0, count: 0 },
    transfer: { total: 0, count: 0 },
    credit: { total: 0, count: 0 },
  }
  let periodTotalAll = 0
  let periodCountAll = 0
  if (summary) {
    for (const method of Object.keys(PAYMENT_LABELS) as PaymentMethod[]) {
      const stat = summary.by_payment_method[method]
      if (!stat) continue
      paymentStats[method] = { total: Number(stat.total), count: stat.count }
      periodTotalAll += Number(stat.total)
      periodCountAll += stat.count
    }
  }

  const activeFilterCount =
    (warehouseFilter !== 'all' ? 1 : 0) +
    (paymentFilter !== 'all' ? 1 : 0) +
    (sortMode !== 'date_desc' ? 1 : 0) +
    (clientQuery.trim() !== '' ? 1 : 0) +
    (productFilter ? 1 : 0)

  const showPaymentTag = sortMode !== 'payment'
  const singleWarehouseId =
    filteredSales.length > 0 && filteredSales.every((s) => s.warehouse_id === filteredSales[0].warehouse_id)
      ? filteredSales[0].warehouse_id
      : null
  const showWarehouseTag = singleWarehouseId === null
  const historyRowColumns = [
    '100px',
    showPaymentTag ? '92px' : null,
    showWarehouseTag ? '1fr' : null,
    '1fr',
    '70px',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={layoutStyles.stack}>
      <div className={layoutStyles.sectionTitle}>
        <h2>Продажи</h2>
        <div className={layoutStyles.pageTitleActions}>
          <div className={layoutStyles.pageTitleActionsDesktop}>
            <Button onClick={() => navigate('/sales/new')}>
              <IconPlus size={16} stroke={1.8} />
              {hasDraft ? 'Продолжить продажу' : 'Новая продажа'}
            </Button>
          </div>
          <div className={layoutStyles.pageTitleActionsMobile}>
            <IconButton
              variant="accent"
              size="lg"
              aria-label={hasDraft ? 'Продолжить продажу' : 'Новая продажа'}
              onClick={() => navigate('/sales/new')}
            >
              <IconPlus size={20} stroke={2} />
            </IconButton>
          </div>
        </div>
      </div>

      <div ref={sentinelRef} style={{ height: 1, marginBottom: -1 }} />
      <div className={[styles.saleFiltersBar, pinned && styles.isPinned].filter(Boolean).join(' ')}>
        <div className={styles.salePeriodRow}>
          <PillTabs
            value={period}
            options={Object.keys(PERIOD_LABELS) as PeriodFilter[]}
            labels={PERIOD_LABELS}
            onChange={(v) => {
              setPeriod(v)
              setSpecificDateFrom('')
              setSpecificDateTo('')
            }}
          />
          <DateInput
            className={[styles.saleDatePicker, specificDateFrom && styles.saleFilterActive].filter(Boolean).join(' ')}
            value={specificDateFrom}
            rangeEnd={specificDateTo}
            max={toISODate(new Date())}
            // не вызывается: с onRangeChange DateInput всегда работает в
            // режиме диапазона (клик на один день дважды даёт from === to)
            onChange={() => {}}
            onRangeChange={(from, to) => {
              setSpecificDateFrom(from)
              setSpecificDateTo(to)
              setPeriod('all')
            }}
          />
        </div>
        <div className={styles.saleFiltersScroll}>
          <input
            className={[styles.saleClientSearch, clientQuery.trim() !== '' && styles.saleFilterActive]
              .filter(Boolean)
              .join(' ')}
            placeholder="Поиск по клиенту"
            aria-label="Поиск по клиенту"
            value={clientQuery}
            onChange={(e) => setClientQuery(e.target.value)}
          />
          <ProductFilterSearch
            value={productFilter}
            onChange={setProductFilter}
            className={styles.saleClientSearch}
            activeClassName={styles.saleFilterActive}
          />
          {warehouses.length > 1 && (
            <label className={styles.saleSortField}>
              <Select
                className={warehouseFilter !== 'all' ? styles.saleFilterActive : undefined}
                value={warehouseFilter === 'all' ? 'all' : String(warehouseFilter)}
                onChange={(v) => setWarehouseFilter(v === 'all' ? 'all' : Number(v))}
                options={[
                  { value: 'all', label: 'Все склады' },
                  ...warehouses.map((w) => ({ value: String(w.id), label: w.name })),
                ]}
              />
            </label>
          )}
          <label className={styles.saleSortField}>
            <Select
              className={sortMode !== 'date_desc' ? styles.saleFilterActive : undefined}
              value={sortMode}
              onChange={(v) => setSortMode(v as SaleSortMode)}
              options={(Object.keys(SALE_SORT_LABELS) as SaleSortMode[]).map((mode) => ({
                value: mode,
                label: SALE_SORT_LABELS[mode],
              }))}
            />
          </label>
          {activeFilterCount > 0 && (
            <ResetFiltersButton
              onClick={() => {
                setPaymentFilter('all')
                setSortMode('date_desc')
                setWarehouseFilter('all')
                setClientQuery('')
                setProductFilter(null)
              }}
            />
          )}
        </div>
      </div>

      {!loading && filteredSales.length > 0 && (
        <div className={[layoutStyles.card, layoutStyles.cardFull, styles.salePeriodSummary].join(' ')}>
          <h3 className={styles.salePeriodSummaryTitle}>Итого</h3>
          <div className={layoutStyles.gridStats}>
            <div className={layoutStyles.stat}>
              <span className={layoutStyles.statLabel}>Выручка</span>
              <span className={layoutStyles.statValue}>{formatMoney(animatedPeriodTotal)} ₽</span>
            </div>
            <div className={layoutStyles.stat}>
              <span className={layoutStyles.statLabel}>Продаж</span>
              <span className={layoutStyles.statValue}>{Math.round(animatedSalesCount)}</span>
            </div>
            <div className={layoutStyles.stat}>
              <span className={layoutStyles.statLabel}>Средний чек</span>
              <span className={layoutStyles.statValue}>{formatMoney(animatedAvgCheck)} ₽</span>
            </div>
          </div>
          <div className={styles.salePaymentBreakdown}>
            <button
              type="button"
              className={[styles.salePaymentItem, paymentFilter === 'all' && styles.salePaymentItemActive]
                .filter(Boolean)
                .join(' ')}
              onClick={() => setPaymentFilter('all')}
            >
              <span className={['badge', styles.salePaymentBadgeAll].join(' ')}>Все способы</span>
              <span>
                {periodCountAll} · {formatMoney(periodTotalAll)} ₽
              </span>
            </button>
            {(Object.keys(PAYMENT_LABELS) as PaymentMethod[]).map((method) => (
              <button
                type="button"
                key={method}
                className={[
                  styles.salePaymentItem,
                  paymentFilter === method && styles.salePaymentItemActive,
                ]
                  .filter(Boolean)
                  .join(' ')}
                onClick={() => setPaymentFilter(method)}
                disabled={paymentStats[method].count === 0}
              >
                <span className={PAYMENT_BADGE_CLASS[method]}>{PAYMENT_LABELS[method]}</span>
                <span>
                  {paymentStats[method].count} · {formatMoney(paymentStats[method].total)} ₽
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {error && <p className={layoutStyles.error}>{error}</p>}

      {!loading && warehouses.length === 0 && (
        <div className={[layoutStyles.card, layoutStyles.cardFull, layoutStyles.onboardingBanner].join(' ')}>
          <div className={layoutStyles.stack} style={{ gap: 2 }}>
            <strong>Добавьте склад — и можно начинать</strong>
            <span className={layoutStyles.textMuted}>
              Склад — это то место, где реально лежит товар (магазин, точка, подсобка). Без него
              некуда принять товар и не с чего продавать.
            </span>
          </div>
          <Link to="/stock">
            <Button>
              <IconPlus size={16} stroke={1.8} /> Добавить склад
            </Button>
          </Link>
        </div>
      )}

      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : filteredSales.length === 0 ? (
        total === 0 ? (
          <EmptyState
            illustration="empty-sales"
            title="Продаж пока нет — начните первую"
            description="Оформите продажу: товар, количество, оплата — и чек готов."
            actionLabel="Новая продажа"
            onAction={() => navigate('/sales/new')}
          />
        ) : (
          <p className={layoutStyles.textMuted}>За этот период продаж нет</p>
        )
      ) : (
        <div key={`${dateRange.from}-${dateRange.to}`} className={layoutStyles.stack} style={{ gap: 16 }}>
          {groups.map((group) => (
            <div className={styles.saleDayGroup} key={group.label}>
              <div className={styles.saleDayHeader}>
                <span>{group.label}</span>
                <span className={styles.saleDayHeaderStats}>
                  <span>
                    {group.count} {pluralizeSales(group.count)}
                  </span>
                  <span className={styles.saleDayHeaderTotal}>{formatMoney(group.total)} ₽</span>
                </span>
              </div>
              <div className={styles.saleHistory}>
                {group.sales.map((s, i) => (
                  <button
                    type="button"
                    className={[styles.saleHistoryRow, styles.saleHistoryRowIn].join(' ')}
                    style={
                      {
                        '--history-row-columns': historyRowColumns,
                        '--row-delay': `${Math.min(i, 12) * 25}ms`,
                      } as CSSProperties
                    }
                    key={s.id}
                    onClick={() => navigate(`/sales/${s.id}`)}
                  >
                    <span className={styles.saleHistoryTotal}>{formatMoney(s.total)} ₽</span>
                    {showPaymentTag && (
                      <span className={PAYMENT_BADGE_CLASS[s.payment_method]}>
                        {PAYMENT_LABELS[s.payment_method]}
                      </span>
                    )}
                    {showWarehouseTag && (
                      <span className={styles.saleHistoryDetail}>
                        <IconBuildingWarehouse size={13} stroke={1.8} />
                        {warehouseName(s.warehouse_id)}
                      </span>
                    )}
                    <span className={styles.saleHistoryDetail}>
                      {clientName(s.client_id) && (
                        <>
                          <IconUsers size={13} stroke={1.8} />
                          {clientName(s.client_id)}
                        </>
                      )}
                    </span>
                    <span className={styles.saleHistoryTime}>
                      {sortMode === 'payment'
                        ? new Date(s.created_at).toLocaleString('ru-RU', {
                            day: 'numeric',
                            month: 'short',
                            hour: '2-digit',
                            minute: '2-digit',
                          })
                        : new Date(s.created_at).toLocaleTimeString('ru-RU', {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ))}
          {sales.length < total && !debouncedClientQuery.trim() && (
            <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? 'Загрузка…' : `Показать ещё (${total - sales.length})`}
            </Button>
          )}
        </div>
      )}

    </div>
  )
}

/** Поиск товара для фильтра списка продаж — печатаете название, выбираете
 * один из подсказанных вариантов, список продаж фильтруется по product_id
 * на сервере (в отличие от поиска по клиенту, который остаётся клиентским). */
function ProductFilterSearch({
  value,
  onChange,
  className,
  activeClassName,
}: {
  value: { id: number; name: string } | null
  onChange: (v: { id: number; name: string } | null) => void
  className?: string
  activeClassName?: string
}) {
  const [query, setQuery] = useState(value?.name ?? '')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [results, setResults] = useState<Product[]>([])
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setQuery(value?.name ?? '')
  }, [value])

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query.trim()), 300)
    return () => clearTimeout(timer)
  }, [query])

  useEffect(() => {
    // выбранный товар не переискивается по своему же названию — только когда
    // пользователь реально печатает что-то новое поверх выбора
    if (!debouncedQuery || debouncedQuery === value?.name) {
      setResults([])
      return
    }
    let cancelled = false
    listProducts({ query: debouncedQuery, limit: 8 })
      .then(({ items }) => {
        if (!cancelled) setResults(items)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [debouncedQuery, value?.name])

  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  function selectProduct(p: Product) {
    onChange({ id: p.id, name: p.name })
    setQuery(p.name)
    setOpen(false)
  }

  function handleQueryChange(next: string) {
    setQuery(next)
    setOpen(true)
    if (value && next !== value.name) onChange(null)
  }

  return (
    <div ref={rootRef} className={styles.saleProductSearch}>
      <input
        // Подсветка "фильтр активен" — только когда товар реально выбран из
        // списка (value), а не просто напечатан текст: иначе рамка загоралась
        // до применения фильтра и создавала впечатление, что он уже сработал.
        className={[className, value && activeClassName].filter(Boolean).join(' ')}
        placeholder="Поиск по товару"
        aria-label="Поиск по товару"
        value={query}
        onChange={(e) => handleQueryChange(e.target.value)}
        onFocus={() => setOpen(true)}
      />
      {open && results.length > 0 && (
        <ul className={styles.saleProductSearchDropdown} role="listbox">
          {results.map((p) => (
            <li key={p.id} role="option" aria-selected={value?.id === p.id}>
              <button type="button" onClick={() => selectProduct(p)}>
                {p.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
