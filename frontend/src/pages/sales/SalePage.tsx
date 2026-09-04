import {
  lazy,
  Suspense,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
} from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { listProducts, getByBarcode, type Product } from '../../entities/product/api'
import { type Warehouse } from '../../entities/inventory/api'
import { searchClients, type Client } from '../../entities/counterparty/api'
import { listClientDebts, type Debt } from '../../entities/debt/api'
import { useCatalog } from '../../app/CatalogContext'
import {
  createSale,
  returnSale,
  getReceipt,
  getReceiptPdf,
  listSales,
  getSalesSummary,
  getSale,
  editSale,
  deleteSale,
  getSaleHistory,
  listSaleReturns,
  type PaymentMethod,
  type SaleItemInput,
  type Sale,
  type SaleHistoryEntry,
  type SaleReturn,
  type SalesSummary,
} from '../../entities/sale/api'
import {
  IconReceiptRefund,
  IconPlus,
  IconMinus,
  IconX,
  IconBuildingWarehouse,
  IconUsers,
  IconBarcode,
  IconChevronRight,
  IconCheck,
  IconBrandWhatsapp,
  IconDownload,
  IconShare,
  IconPencil,
  IconTrash,
  type Icon as TablerIcon,
} from '@tabler/icons-react'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
import { QuickNewClientForm } from '../../shared/ui/QuickNewClientForm'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { StockWarningIcon } from '../../shared/ui/StockWarningIcon'
import { InfoHint } from '../../shared/ui/InfoHint'
import { ResetFiltersButton } from '../../shared/ui/ResetFiltersButton'
import { PillTabs } from '../../shared/ui/PillTabs'
import { HistoryDisclosure } from '../../shared/ui/HistoryDisclosure'
import { isBarcodeScannerSupported } from '../../entities/barcode/barcodeSupport'
import { queueSale } from '../../shared/offline/outbox'

const BarcodeScanner = lazy(() =>
  import('../../entities/barcode/BarcodeScanner').then((m) => ({ default: m.BarcodeScanner })),
)
import { useAnimatedNumber } from '../../shared/lib/useAnimatedNumber'
import {
  formatQuantity,
  formatMoney,
  pluralizeSales,
  lineTotalCents,
  centsToMoney,
  normalizeDecimalInput,
  isLowStock,
  isOutOfStock,
} from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from '../../entities/debt/debtStatus'
import { useAuth } from '../../app/AuthContext'
import { scopedKey } from '../../shared/lib/scopedStorage'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './SalePage.module.css'

const PAGE_SIZE = 50
const PRODUCTS_PAGE_SIZE = 32

interface CartLine {
  product: Product
  quantity: string
  price: string
}

interface SaleDraft {
  warehouseId: number | null
  cart: CartLine[]
  payment: PaymentMethod
  discount: string
  discountMode: 'amount' | 'percent'
  clientId: number | null
}

function loadDraft(): SaleDraft | null {
  try {
    const raw = localStorage.getItem(scopedKey('sale-draft'))
    return raw ? (JSON.parse(raw) as SaleDraft) : null
  } catch {
    return null
  }
}

function saveDraft(draft: SaleDraft) {
  try {
    localStorage.setItem(scopedKey('sale-draft'), JSON.stringify(draft))
  } catch {
    // localStorage недоступен (приватный режим и т.п.) — черновик просто не переживёт перезагрузку
  }
}

function clearDraft() {
  localStorage.removeItem(scopedKey('sale-draft'))
}

const PAYMENT_LABELS: Record<PaymentMethod, string> = {
  cash: 'Наличные',
  transfer: 'Перевод',
  credit: 'В долг',
}

const PAYMENT_BADGE_CLASS: Record<PaymentMethod, string> = {
  cash: 'badge accent',
  transfer: 'badge',
  credit: 'badge danger',
}

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

type SortMode = 'name' | 'price_asc' | 'price_desc' | 'stock_desc'

const SORT_LABELS: Record<SortMode, string> = {
  name: 'По названию',
  price_asc: 'Цена: сначала дешёвые',
  price_desc: 'Цена: сначала дорогие',
  stock_desc: 'По остатку',
}

export function SalePage() {
  const { warehouses, ensureWarehouses } = useCatalog()
  const [sales, setSales] = useState<Sale[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const [showNewSale, setShowNewSale] = useState(() => searchParams.get('open') === '1')
  const [hasDraft] = useState(() => loadDraft() !== null)
  const [savedSaleNotice, setSavedSaleNotice] = useState<Sale | null>(null)

  useEffect(() => {
    if (!savedSaleNotice) return
    const timer = window.setTimeout(() => setSavedSaleNotice(null), 4000)
    return () => window.clearTimeout(timer)
  }, [savedSaleNotice])

  useEffect(() => {
    if (searchParams.get('open') !== '1') return
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete('open')
      return next
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // переход с другой страницы (например «Долги») на карточку конкретной продажи
  useEffect(() => {
    const openSaleId = searchParams.get('openSale')
    if (!openSaleId) return
    getSale(Number(openSaleId))
      .then(setSelectedSale)
      .catch(() => {})
      .finally(() => {
        setSearchParams((prev) => {
          const next = new URLSearchParams(prev)
          next.delete('openSale')
          return next
        })
      })
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
  const [selectedSale, setSelectedSale] = useState<Sale | null>(null)
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
        <Button onClick={() => setShowNewSale(true)}>
          <IconPlus size={16} stroke={1.8} />
          {hasDraft ? 'Продолжить продажу' : 'Новая продажа'}
        </Button>
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
        <p className={layoutStyles.textMuted}>
          {total === 0 ? 'Продаж пока нет — начните первую' : 'За этот период продаж нет'}
        </p>
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
                    onClick={() => setSelectedSale(s)}
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

      {selectedSale && (
        <LastSaleCard
          sale={selectedSale}
          warehouses={warehouses}
          clients={clients}
          onDone={() => setSelectedSale(null)}
          onUpdated={load}
        />
      )}

      {showNewSale && (
        <NewSaleForm
          clients={clients}
          onClientsChange={setClients}
          onClose={() => setShowNewSale(false)}
          onDone={(sale) => {
            setShowNewSale(false)
            setSavedSaleNotice(sale)
            load()
          }}
        />
      )}

      {savedSaleNotice && (
        <div className={styles.saleSavedToast} role="status">
          Продажа №{savedSaleNotice.id} на {formatMoney(savedSaleNotice.total)} ₽ — сохранена
          <button
            type="button"
            className={styles.saleSavedToastClose}
            onClick={() => setSavedSaleNotice(null)}
            aria-label="Закрыть"
          >
            ×
          </button>
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

function NewSaleForm({
  clients: initialClients,
  onClientsChange,
  onClose,
  onDone,
}: {
  clients: Client[]
  onClientsChange: (clients: Client[]) => void
  onClose: () => void
  onDone: (sale: Sale) => void
}) {
  const draft = useMemo(() => loadDraft(), [])
  const {
    categories,
    units,
    stock,
    warehouses,
    ensureCategories,
    ensureUnits,
    ensureStock,
    ensureWarehouses,
    refresh: refreshCatalog,
  } = useCatalog()

  const [products, setProducts] = useState<Product[]>([])
  const [productsTotal, setProductsTotal] = useState(0)
  const [productsLoading, setProductsLoading] = useState(false)
  const [productsLoadingMore, setProductsLoadingMore] = useState(false)
  const [warehouseId, setWarehouseId] = useState<number | null>(draft?.warehouseId ?? null)
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [categoryId, setCategoryId] = useState<number | null>(null)
  const [sortMode, setSortMode] = useState<SortMode>('name')
  const [showAllStock, setShowAllStock] = useState(false)
  const [cart, setCart] = useState<CartLine[]>(draft?.cart ?? [])
  const [maxReachedProductId, setMaxReachedProductId] = useState<number | null>(null)
  const maxReachedTimerRef = useRef<number | undefined>(undefined)

  useEffect(() => () => window.clearTimeout(maxReachedTimerRef.current), [])
  const [payment, setPayment] = useState<PaymentMethod>(draft?.payment ?? 'cash')
  const [debtDueDate, setDebtDueDate] = useState('')
  const [cashReceived, setCashReceived] = useState('')
  const [discount, setDiscount] = useState(draft?.discount ?? '0')
  const [discountMode, setDiscountMode] = useState<'amount' | 'percent'>(
    draft?.discountMode ?? 'amount',
  )
  const clients = initialClients
  const [clientId, setClientId] = useState<number | null>(draft?.clientId ?? null)
  const [showNewClientForm, setShowNewClientForm] = useState(false)
  const [showScanner, setShowScanner] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)
  const [showClearConfirm, setShowClearConfirm] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [offlineQueued, setOfflineQueued] = useState<{ itemsCount: number; total: string } | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(timer)
  }, [query])

  // "По остатку" сервер не умеет (остатки — отдельная таблица по складам) — просим
  // sort=name вместо него, чтобы offset-пагинация была стабильной между страницами
  // (без ORDER BY на сервере одна и та же страница могла бы вернуть разный набор
  // строк при повторном запросе), а порядок "по остатку" считаем в filtered ниже.
  const serverSort = sortMode === 'stock_desc' ? 'name' : sortMode

  useEffect(() => {
    setProductsLoading(true)
    setProducts([])
    listProducts({ query: debouncedQuery, categoryId, sort: serverSort, limit: PRODUCTS_PAGE_SIZE, offset: 0 })
      .then(({ items, total }) => {
        setProducts(items)
        setProductsTotal(total)
      })
      .catch(() => {})
      .finally(() => setProductsLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQuery, categoryId, serverSort])

  function loadMoreProducts() {
    if (productsLoadingMore || products.length >= productsTotal) return
    setProductsLoadingMore(true)
    listProducts({
      query: debouncedQuery,
      categoryId,
      sort: serverSort,
      limit: PRODUCTS_PAGE_SIZE,
      offset: products.length,
    })
      .then(({ items, total }) => {
        setProducts((prev) => [...prev, ...items])
        setProductsTotal(total)
      })
      .catch(() => {})
      .finally(() => setProductsLoadingMore(false))
  }

  const productsSentinelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = productsSentinelRef.current
    if (!el) return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) loadMoreProducts()
    })
    observer.observe(el)
    return () => observer.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [products.length, productsTotal, productsLoadingMore, debouncedQuery, categoryId, serverSort])

  useEffect(() => {
    ensureCategories().catch(() => {})
    ensureUnits().catch(() => {})
    ensureStock().catch(() => {})
    ensureWarehouses()
      .then((list) => {
        if (list.length > 0 && warehouseId == null) setWarehouseId(list[0].id)
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Черновик переживает закрытие модалки/перезагрузку страницы, пока продажа не проведена
  useEffect(() => {
    if (offlineQueued) return
    if (cart.length === 0) {
      clearDraft()
      return
    }
    saveDraft({ warehouseId, cart, payment, discount, discountMode, clientId })
  }, [warehouseId, cart, payment, discount, discountMode, clientId, offlineQueued])

  async function handleScan(code: string) {
    setShowScanner(false)
    setScanError(null)
    try {
      const product = await getByBarcode(code)
      if (product) {
        addToCart(product)
      } else {
        setScanError(`Товар со штрихкодом ${code} не найден`)
      }
    } catch {
      setScanError('Не удалось найти товар по штрихкоду')
    }
  }

  const handleScanRef = useRef(handleScan)
  handleScanRef.current = handleScan

  // Аппаратные USB/Bluetooth-сканеры эмулируют клавиатуру: печатают все цифры
  // штрихкода за доли секунды и завершают вводом Enter. Обычный человек набирает
  // медленнее — по паузе между нажатиями (>60мс) отличаем сканер от ручного ввода.
  useEffect(() => {
    let buffer = ''
    let lastKeyTime = 0

    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null
      const isEditableTarget =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target?.isContentEditable

      const now = Date.now()
      const gap = now - lastKeyTime
      lastKeyTime = now

      if (gap > 60) {
        buffer = ''
      }

      if (e.key === 'Enter') {
        if (buffer.length >= 4) {
          if (isEditableTarget) e.preventDefault()
          const code = buffer
          buffer = ''
          handleScanRef.current(code)
        }
        return
      }

      if (/^\d$/.test(e.key)) {
        buffer += e.key
      } else if (!isEditableTarget) {
        // не цифра и не текстовое поле — постороннее нажатие сбрасывает буфер
        buffer = ''
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const stockFor = (productId: number) =>
    warehouseId == null
      ? null
      : stock.find((s) => s.product_id === productId && s.warehouse_id === warehouseId)?.available ?? '0'
  const reservedFor = (productId: number) =>
    warehouseId == null
      ? 0
      : Number(stock.find((s) => s.product_id === productId && s.warehouse_id === warehouseId)?.reserved ?? '0')

  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code
  const isFractional = (code: string) => units.find((u) => u.code === code)?.fractional ?? false

  const filtered = useMemo(() => {
    // categoryId, query и name/price_* сортировка уже применены на сервере —
    // здесь остаются только showAllStock-фильтр и sort=stock_desc, которым
    // нужны остатки по складу, а их на сервере для этого списка нет.
    // Сортирует только уже загруженную страницу — при подгрузке следующей
    // порядок "по остатку" внутри неё не переплетается с предыдущей.
    let list = products
    if (warehouseId != null && !showAllStock) {
      list = list.filter((p) => Number(stockFor(p.id) ?? 0) > 0)
    }
    if (sortMode !== 'stock_desc') return list
    const sorted = [...list]
    sorted.sort((a, b) => Number(stockFor(b.id) ?? 0) - Number(stockFor(a.id) ?? 0))
    return sorted
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [products, showAllStock, sortMode, stock, warehouseId])

  const cartQtyByProduct = useMemo(
    () => new Map(cart.map((l) => [l.product.id, l.quantity])),
    [cart],
  )

  function notifyMaxReached(productId: number) {
    setMaxReachedProductId(productId)
    window.clearTimeout(maxReachedTimerRef.current)
    maxReachedTimerRef.current = window.setTimeout(() => setMaxReachedProductId(null), 2000)
  }

  function addToCart(product: Product) {
    const available = stockFor(product.id)
    const max = available !== null ? Number(available) : null
    const fractional = isFractional(product.unit_code)
    const clamp = (value: number) => (fractional ? value : Math.floor(value))
    let blocked = false
    setCart((prev) => {
      const existing = prev.find((l) => l.product.id === product.id)
      if (existing) {
        const current = Number(existing.quantity)
        if (max !== null && current >= max) {
          blocked = true
          return prev
        }
        const next = clamp(max !== null ? Math.min(current + 1, max) : current + 1)
        return prev.map((l) =>
          l.product.id === product.id ? { ...l, quantity: String(next) } : l,
        )
      }
      if (max !== null && max <= 0) {
        blocked = true
        return prev
      }
      const initial = clamp(max !== null ? Math.min(1, max) : 1)
      if (initial <= 0) {
        blocked = true
        return prev
      }
      return [...prev, { product, quantity: String(initial), price: product.retail_price }]
    })
    if (blocked) notifyMaxReached(product.id)
  }

  function updateLine(productId: number, field: 'quantity' | 'price', rawValue: string, max?: number | null) {
    const normalized = normalizeDecimalInput(rawValue)
    if (normalized === null) return
    setCart((prev) =>
      prev.map((l) => {
        if (l.product.id !== productId) return l
        let value = normalized
        if (field === 'quantity' && !isFractional(l.product.unit_code) && value.includes('.')) {
          value = value.split('.')[0] || '0'
        }
        if (field === 'quantity' && max != null && value !== '' && Number(value) > max) {
          value = isFractional(l.product.unit_code) ? String(max) : String(Math.floor(max))
        }
        return { ...l, [field]: value }
      }),
    )
  }

  function stepLineQuantity(productId: number, delta: number, max: number | null) {
    let blocked = false
    setCart((prev) =>
      prev.map((l) => {
        if (l.product.id !== productId) return l
        const current = Number(l.quantity || 0)
        let next = current + delta
        if (max !== null && next > max) {
          next = max
          if (current >= max) blocked = true
        }
        next = Math.max(0, next)
        const fractional = isFractional(l.product.unit_code)
        const quantity = fractional
          ? (Number.isInteger(next) ? next.toFixed(1) : String(next))
          : String(Math.round(next))
        return { ...l, quantity }
      }),
    )
    if (blocked) notifyMaxReached(productId)
  }

  function removeLine(productId: number) {
    setCart((prev) => prev.filter((l) => l.product.id !== productId))
  }

  function clearCart() {
    clearDraft()
    setCart([])
    setDiscount('0')
    setDiscountMode('amount')
    setClientId(null)
    setPayment('cash')
    setDebtDueDate('')
    setCashReceived('')
    setError(null)
  }

  function handleClear() {
    if (cart.length > 0) {
      setShowClearConfirm(true)
      return
    }
    clearCart()
  }

  const subtotalCents = cart.reduce((sum, l) => sum + lineTotalCents(l.quantity, l.price), 0)
  const subtotal = centsToMoney(subtotalCents)
  const discountAmountCents =
    discountMode === 'percent'
      ? Math.round((subtotalCents * Number(discount || 0)) / 100)
      : Math.round(Number(discount || 0) * 100)
  const discountAmount = centsToMoney(discountAmountCents)
  const totalCents = Math.max(0, subtotalCents - discountAmountCents)
  const total = centsToMoney(totalCents)
  const cashReceivedCents = Math.round(Number(cashReceived || 0) * 100)
  const changeCents = cashReceivedCents - totalCents
  const change = centsToMoney(Math.max(0, changeCents))

  async function handleCheckout() {
    if (!warehouseId || cart.length === 0) return
    if (payment === 'credit' && !clientId) {
      setError('Для продажи в долг выберите клиента')
      return
    }
    if (payment === 'credit' && !debtDueDate) {
      setError('Для продажи в долг укажите срок «Долг до»')
      return
    }
    const overStockLine = cart.find((l) => {
      const available = stockFor(l.product.id)
      return available !== null && Number(l.quantity || 0) > Number(available)
    })
    if (overStockLine) {
      setError(`«${overStockLine.product.name}» — количество больше остатка на складе`)
      return
    }
    setError(null)
    setSaving(true)
    const items: SaleItemInput[] = cart.map((l) => ({
      product_id: l.product.id,
      quantity: l.quantity,
      price: l.price,
    }))
    const cashReceivedValue =
      payment === 'cash' && cashReceived && cashReceivedCents >= totalCents ? cashReceived : null
    try {
      const sale = await createSale({
        warehouse_id: warehouseId,
        payment_method: payment,
        items,
        discount: discountAmount.toFixed(2),
        client_id: clientId,
        cash_received: cashReceivedValue,
        debt_due_date: payment === 'credit' ? debtDueDate : null,
      })
      clearDraft()
      refreshCatalog(['stock']).catch(() => {})
      onDone(sale)
    } catch (err) {
      // Сеть недоступна — сохраняем в очередь (включая продажи в долг с debt_due_date).
      const isNetworkFailure = !(err instanceof ApiError) && (!navigator.onLine || err instanceof TypeError)
      if (isNetworkFailure && (payment !== 'credit' || (clientId && debtDueDate))) {
        await queueSale({
          warehouse_id: warehouseId,
          payment_method: payment,
          items,
          discount: discountAmount.toFixed(2),
          client_id: clientId,
          cash_received: cashReceivedValue,
          debt_due_date: payment === 'credit' ? debtDueDate : null,
        })
        clearDraft()
        setOfflineQueued({ itemsCount: items.length, total: total.toFixed(2) })
        setCart([])
        setDiscount('0')
        setClientId(null)
        setDebtDueDate('')
        setCashReceived('')
      } else {
        setError(err instanceof ApiError ? err.message : 'Не удалось провести продажу')
      }
    } finally {
      setSaving(false)
    }
  }

  if (offlineQueued) {
    return (
      <Modal title="Продажа сохранена локально" onClose={onClose} size="full">
        <div className={layoutStyles.stack} style={{ textAlign: 'center', padding: '24px 12px' }}>
          <p>
            Нет подключения к интернету. Продажа на сумму {formatMoney(offlineQueued.total)} (позиций в чеке:{' '}
            {offlineQueued.itemsCount}) сохранена на устройстве и отправится на сервер автоматически, как
            только появится сеть.
          </p>
          <Button onClick={onClose} style={{ alignSelf: 'center' }}>Понятно</Button>
        </div>
      </Modal>
    )
  }

  return (
    <>
    <Modal
      title="Новая продажа"
      onClose={onClose}
      size="full"
      footer={
        <>
          <Button onClick={handleCheckout} disabled={saving || !warehouseId || cart.length === 0}>
            {saving ? 'Проведение…' : 'Провести продажу'}
          </Button>
          <Button variant="secondary" onClick={handleClear} disabled={cart.length === 0}>
            Очистить
          </Button>
          <span className={styles.modalFooterTotal}>
            {discountAmount > 0 && (
              <span className={styles.modalFooterBreakdown}>
                {formatMoney(subtotal)} ₽ − {formatMoney(discountAmount)} ₽ ={' '}
              </span>
            )}
            Итого: <strong>{formatMoney(total)} ₽</strong>
          </span>
        </>
      }
    >
      <div className={layoutStyles.stack}>
      <div className={styles.saleSearchPanel}>
        <div>
          <div className={styles.saleSearchRow}>
            <IconBarcode size={18} stroke={1.8} className={styles.saleSearchIcon} />
            <input
              className={styles.saleSearchInput}
              placeholder={
                isBarcodeScannerSupported()
                  ? 'Найти товар по названию или отсканировать штрихкод…'
                  : 'Найти товар по названию…'
              }
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {isBarcodeScannerSupported() && (
              <Button
                variant="secondary"
                className={styles.saleScanButton}
                onClick={() => setShowScanner(true)}
              >
                <IconBarcode size={16} stroke={1.8} /> Скан
              </Button>
            )}
          </div>
        </div>

        <div className={styles.saleFiltersRow}>
          {warehouses.length > 1 && (
            <label className={styles.saleFilterField}>
              <span className={styles.saleFilterLabel}>Склад</span>
              <Select
                value={String(warehouseId ?? '')}
                onChange={(v) => setWarehouseId(Number(v))}
                options={warehouses.map((w) => ({ value: String(w.id), label: w.name }))}
              />
            </label>
          )}

          {categories.length > 0 && (
            <label className={styles.saleFilterField}>
              <span className={styles.saleFilterLabel}>Категория</span>
              <Select
                value={String(categoryId ?? '')}
                onChange={(v) => setCategoryId(v ? Number(v) : null)}
                options={[
                  { value: '', label: 'Все' },
                  ...categories.map((c) => ({ value: String(c.id), label: c.name })),
                ]}
              />
            </label>
          )}

          <label className={styles.saleFilterField}>
            <span className={styles.saleFilterLabel}>Сортировка</span>
            <Select
              value={sortMode}
              onChange={(v) => setSortMode(v as SortMode)}
              options={Object.entries(SORT_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </label>

          {warehouseId != null && (
            <label className={styles.saleCheckbox}>
              <input
                type="checkbox"
                checked={showAllStock}
                onChange={(e) => setShowAllStock(e.target.checked)}
              />
              Показать и то, чего нет на складе
            </label>
          )}
        </div>

        {scanError && <p className={layoutStyles.error}>{scanError}</p>}
      </div>

      <div className={styles.saleResultsPanel}>
        <div className={styles.saleResultsHeader}>
          <span>Товары</span>
          {/* Счётчик — по реально видимому списку (filtered), а не по серверному
              productsTotal: сервер считает по query/категории без учёта склада,
              а warehouseId+!showAllStock ещё прячет товары без остатка — раньше
              счётчик и список расходились ("1 найдено" при пустом списке). */}
          {!productsLoading && <span className={layoutStyles.textMuted}>{filtered.length} найдено</span>}
        </div>

        {productsLoading ? (
          <p className={layoutStyles.textMuted}>Загрузка…</p>
        ) : filtered.length === 0 && products.length > 0 && warehouseId != null && !showAllStock ? (
          <p className={layoutStyles.textMuted}>
            {products.length === 1 ? 'Найден 1 товар' : `Найдено товаров: ${products.length}`}, но
            {products.length === 1 ? ' его' : ' их'} нет на этом складе —{' '}
            <button type="button" className={layoutStyles.disclosureLink} onClick={() => setShowAllStock(true)}>
              показать
            </button>
          </p>
        ) : filtered.length === 0 ? (
          <p className={layoutStyles.textMuted}>Ничего не найдено</p>
        ) : (
          <div className={layoutStyles.productGrid}>
            {filtered.map((p) => {
              const qty = stockFor(p.id)
              const reserved = reservedFor(p.id)
              const inCartQty = cartQtyByProduct.get(p.id)
              return (
                <div
                  key={p.id}
                  role="button"
                  tabIndex={0}
                  className={[layoutStyles.productTile, inCartQty && layoutStyles.productTileInCart]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => addToCart(p)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      addToCart(p)
                    }
                  }}
                >
                  <ProductPhoto src={p.photo} />
                  <div className={layoutStyles.productTileBody}>
                    <span className={layoutStyles.productTileName}>{p.name}</span>
                    <span className={layoutStyles.productTileMeta}>
                      <span className={layoutStyles.productTilePriceLabel}>Цена за {unitName(p.unit_code)}:</span>
                      <span className={layoutStyles.productTilePrice}>{formatMoney(p.retail_price)} ₽</span>
                    </span>
                    {qty !== null && (
                      <span
                        className={[
                          layoutStyles.productTileStock,
                          isOutOfStock(qty) ? layoutStyles.productTileStockOut : layoutStyles.productTileStockIn,
                        ].join(' ')}
                      >
                        <span className={layoutStyles.productTileStockLabel}>
                          Остаток:
                          {reserved > 0 && (
                            <InfoHint
                              text={`${formatQuantity(String(reserved))} ${unitName(p.unit_code)} зарезервировано на заказ клиента и недоступно для продажи — освободится, когда заказ выдадут или отменят.`}
                            />
                          )}
                        </span>
                        <span className={layoutStyles.productTileStockValueWrap}>
                          <span className={layoutStyles.productTileStockValue}>
                            {formatQuantity(qty)} {unitName(p.unit_code)}
                          </span>
                          {isLowStock(qty, p.min_stock) && <StockWarningIcon />}
                        </span>
                      </span>
                    )}
                  </div>
                  <span
                    className={[
                      layoutStyles.productTileCartBadge,
                      !inCartQty && layoutStyles.productTileCartBadgeHidden,
                    ]
                      .filter(Boolean)
                      .join(' ')}
                  >
                    {inCartQty ? (
                      <>
                        {formatQuantity(inCartQty)}
                        <IconButton
                          variant="neutral"
                          className={layoutStyles.productTileRemove}
                          onClick={(e) => {
                            e.stopPropagation()
                            removeLine(p.id)
                          }}
                          aria-label="Убрать из чека"
                        >
                          <IconX size={10} stroke={2} />
                        </IconButton>
                      </>
                    ) : (
                      ' '
                    )}
                  </span>
                  {maxReachedProductId === p.id && (
                    <span className={layoutStyles.productTileMaxReached}>Больше нет на складе</span>
                  )}
                </div>
              )
            })}
          </div>
        )}
        {!productsLoading && products.length < productsTotal && (
          <div ref={productsSentinelRef} className={layoutStyles.stack} style={{ alignItems: 'center' }}>
            <span className={layoutStyles.textMuted}>
              {productsLoadingMore ? 'Загрузка…' : 'Прокрутите ниже для ещё товаров'}
            </span>
          </div>
        )}
      </div>

      {showScanner && (
        <Modal title="Сканировать штрихкод" onClose={() => setShowScanner(false)}>
          <Suspense fallback={<p className={layoutStyles.textMuted}>Загрузка сканера…</p>}>
            <BarcodeScanner onDetected={handleScan} onClose={() => setShowScanner(false)} />
          </Suspense>
        </Modal>
      )}

      {cart.length > 0 && (
        <div className={[layoutStyles.stack, layoutStyles.card, layoutStyles.cardFull].join(' ')}>
          <div className={layoutStyles.sectionTitle}>
            <h3>Чек</h3>
            <span className={layoutStyles.textMuted}>{cart.length} поз.</span>
          </div>

          <div className={styles.cartList}>
            {cart.map((line) => {
              const lineTotal = centsToMoney(lineTotalCents(line.quantity, line.price))
              const available = stockFor(line.product.id)
              const availableNum = available !== null ? Number(available) : null
              const overStock = availableNum !== null && Number(line.quantity || 0) > availableNum
              return (
                <div key={line.product.id} className={styles.cartRow}>
                  <IconButton
                    variant="neutral"
                    className={styles.cartRemoveBtn}
                    onClick={() => removeLine(line.product.id)}
                    aria-label="Убрать из чека"
                  >
                    <IconX size={14} stroke={2} />
                  </IconButton>

                  <div className={styles.cartRowName}>
                    <div>{line.product.name}</div>
                    {availableNum !== null && (
                      <div className={styles.cartTableStock}>
                        Остаток: {formatQuantity(availableNum)} {unitName(line.product.unit_code)}
                      </div>
                    )}
                  </div>

                  <div className={styles.cartRowFields}>
                    <label className={styles.cartField}>
                      <span className={styles.cartFieldLabel}>Кол-во</span>
                      <div className={styles.cartQtyStepper}>
                        <IconButton
                          variant="muted"
                          className={styles.cartQtyStep}
                          onClick={() => stepLineQuantity(line.product.id, -1, availableNum)}
                          aria-label="Уменьшить количество"
                        >
                          <IconMinus size={12} stroke={2} />
                        </IconButton>
                        <input
                          type="text"
                          inputMode="decimal"
                          className={overStock ? styles.cartInputWarning : undefined}
                          value={line.quantity}
                          onChange={(e) => updateLine(line.product.id, 'quantity', e.target.value, availableNum)}
                        />
                        <IconButton
                          variant="muted"
                          className={styles.cartQtyStep}
                          onClick={() => stepLineQuantity(line.product.id, 1, availableNum)}
                          aria-label="Увеличить количество"
                        >
                          <IconPlus size={12} stroke={2} />
                        </IconButton>
                      </div>
                      {overStock && availableNum !== null && (
                        <div className={styles.cartTableWarning}>
                          больше остатка ({formatQuantity(availableNum)})
                        </div>
                      )}
                      {maxReachedProductId === line.product.id && (
                        <div className={styles.cartTableMaxReached}>Больше нет на складе</div>
                      )}
                    </label>

                    <label className={styles.cartField}>
                      <span className={styles.cartFieldLabel}>Цена за шт.</span>
                      <div className={styles.cartPriceInputWrap}>
                        <input
                          type="text"
                          inputMode="decimal"
                          className={styles.cartPriceInput}
                          value={line.price}
                          onChange={(e) => updateLine(line.product.id, 'price', e.target.value)}
                        />
                        <span className={styles.cartTablePriceSuffix}>₽</span>
                      </div>
                    </label>

                    <div className={styles.cartField}>
                      <span className={styles.cartFieldLabel}>Сумма</span>
                      <div className={styles.cartTableTotal}>{formatMoney(lineTotal)} ₽</div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          <div className={styles.saleCheckoutSection}>
            <div className={styles.saleCheckoutRow}>
              <label className={[layoutStyles.field, styles.saleDiscountField].join(' ')}>
                Скидка
                <div className={styles.saleDiscountRow}>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={discount}
                    onChange={(e) => {
                      const normalized = normalizeDecimalInput(e.target.value)
                      if (normalized !== null) setDiscount(normalized)
                    }}
                  />
                  <div className={styles.saleDiscountToggle}>
                    <Button
                      variant={discountMode === 'amount' ? 'primary' : 'secondary'}
                      onClick={() => setDiscountMode('amount')}
                    >
                      ₽
                    </Button>
                    <Button
                      variant={discountMode === 'percent' ? 'primary' : 'secondary'}
                      onClick={() => setDiscountMode('percent')}
                    >
                      %
                    </Button>
                  </div>
                </div>
                {discountMode === 'percent' && Number(discount) > 0 && (
                  <span className={layoutStyles.textMuted}>= {formatMoney(discountAmount)} ₽</span>
                )}
              </label>

              {/* div, а не label — иначе клик мимо Select (по пустому месту в блоке)
                  браузер трактует как implicit label click и открывает список сам */}
              <div className={[layoutStyles.field, styles.salePaymentField].join(' ')}>
                Оплата
                <Select
                  value={payment}
                  onChange={(v) => setPayment(v as PaymentMethod)}
                  options={Object.entries(PAYMENT_LABELS).map(([value, label]) => ({ value, label }))}
                />
              </div>

              {payment === 'cash' && (
                <label className={[layoutStyles.field, styles.saleReceivedField].join(' ')}>
                  Получено
                  <input
                    type="text"
                    inputMode="decimal"
                    placeholder={formatMoney(total)}
                    value={cashReceived}
                    onChange={(e) => {
                      const normalized = normalizeDecimalInput(e.target.value)
                      if (normalized !== null) setCashReceived(normalized)
                    }}
                  />
                  {cashReceivedCents > 0 && (
                    <span className={changeCents < 0 ? styles.saleChangeShort : layoutStyles.textMuted}>
                      {changeCents >= 0
                        ? `Сдача: ${formatMoney(change)} ₽`
                        : `Не хватает: ${formatMoney(centsToMoney(-changeCents))} ₽`}
                    </span>
                  )}
                </label>
              )}
            </div>

            {/* div, а не label — иначе клик мимо Select (по пустому месту в блоке)
                браузер трактует как implicit label click и открывает список сам */}
            <div className={[layoutStyles.field, styles.saleClientField].join(' ')}>
              Клиент
              {payment === 'credit' && !clientId && (
                <span className={styles.saleClientRequired}> — обязательно для продажи в долг</span>
              )}
              <div className={styles.saleClientRow}>
                <Select
                  required={payment === 'credit'}
                  value={String(clientId ?? '')}
                  onChange={(v) => setClientId(v ? Number(v) : null)}
                  options={[
                    { value: '', label: 'Без клиента' },
                    ...clients.map((c) => ({ value: String(c.id), label: c.name })),
                  ]}
                />
                <QuickNewClientForm
                  open={showNewClientForm}
                  onOpenChange={setShowNewClientForm}
                  trigger={
                    <Button variant="secondary" onClick={() => setShowNewClientForm(true)}>
                      <IconPlus size={16} stroke={1.8} /> Клиент
                    </Button>
                  }
                  onCreated={(client) => {
                    onClientsChange([...clients, client])
                    setClientId(client.id)
                    setShowNewClientForm(false)
                  }}
                />
              </div>
            </div>

            {payment === 'credit' && (
              <div className={[layoutStyles.field, styles.saleDebtDueField].join(' ')}>
                Долг до
                <DateInput
                  required
                  value={debtDueDate}
                  min={new Date().toISOString().slice(0, 10)}
                  onChange={setDebtDueDate}
                />
              </div>
            )}
          </div>

          {error && <p className={layoutStyles.error}>{error}</p>}
        </div>
      )}
      </div>
    </Modal>
    {showClearConfirm && (
      <ConfirmDialog
        title="Очистить чек?"
        message="Набранные товары будут удалены."
        confirmLabel="Очистить"
        danger
        onConfirm={clearCart}
        onClose={() => setShowClearConfirm(false)}
      />
    )}
    </>
  )
}

const SALE_HISTORY_ACTION_LABELS: Record<string, string> = {
  'sale.create': 'Продажа создана',
  'sale.return': 'Оформлен возврат',
  'sale.edit': 'Изменены данные продажи',
  'sale.delete': 'Продажа удалена',
}

const SALE_HISTORY_ACTION_ICONS: Record<string, TablerIcon> = {
  'sale.create': IconCheck,
  'sale.edit': IconPencil,
  'sale.delete': IconTrash,
  'sale.return': IconReceiptRefund,
}

function formatSaleHistoryDetail(entry: SaleHistoryEntry): string | null {
  const d = entry.details
  switch (entry.action) {
    case 'sale.create': {
      const method = d.payment_method as PaymentMethod | undefined
      return `${formatMoney(String(d.total ?? '0'))} ₽${method ? ` · ${PAYMENT_LABELS[method]}` : ''}`
    }
    case 'sale.return':
      return `Возврат на ${formatMoney(String(d.refund ?? '0'))} ₽`
    case 'sale.delete':
      return `Сумма продажи ${formatMoney(String(d.total ?? '0'))} ₽`
    default:
      return null
  }
}

function LastSaleCard({
  sale: initialSale,
  warehouses,
  clients,
  onDone,
  onUpdated,
}: {
  sale: Sale
  warehouses: Warehouse[]
  clients: Client[]
  onDone: () => void
  onUpdated: () => void
}) {
  const { user } = useAuth()
  const {
    products,
    units,
    employees,
    ensureProducts,
    ensureUnits,
    ensureEmployees,
    refresh: refreshCatalog,
  } = useCatalog()
  const [sale, setSale] = useState(initialSale)
  const [returns, setReturns] = useState<SaleReturn[]>([])
  const [clientDebt, setClientDebt] = useState<Debt | null>(null)
  const [showReturn, setShowReturn] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [quantities, setQuantities] = useState<Record<number, string>>(() =>
    Object.fromEntries(sale.lines.map((l) => [l.id, ''])),
  )
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [done, setDone] = useState(false)
  const [receiptError, setReceiptError] = useState<string | null>(null)
  const [sendingReceipt, setSendingReceipt] = useState(false)
  const [sharingReceipt, setSharingReceipt] = useState(false)
  const [downloadingReceipt, setDownloadingReceipt] = useState(false)
  const canShareFiles = typeof navigator.share === 'function' && typeof navigator.canShare === 'function'

  useEffect(() => {
    ensureProducts().catch(() => {})
    ensureUnits().catch(() => {})
    ensureEmployees().catch(() => {})
    listSaleReturns(sale.id).then(setReturns).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sale.id])

  useEffect(() => {
    if (sale.payment_method !== 'credit' || sale.client_id == null) {
      setClientDebt(null)
      return
    }
    listClientDebts(sale.client_id)
      .then((summary) => setClientDebt(summary.debts.find((d) => d.sale_id === sale.id) ?? null))
      .catch(() => {})
  }, [sale.payment_method, sale.client_id, sale.id])

  const productName = (id: number) => products.find((p) => p.id === id)?.name ?? `Товар #${id}`
  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code
  const warehouseName = (id: number) => warehouses.find((w) => w.id === id)?.name ?? `#${id}`
  const client = sale.client_id != null ? clients.find((c) => c.id === sale.client_id) : null
  const seller = employees.find((e) => e.id === sale.seller_id)

  const alreadyReturned = (saleLineId: number) =>
    returns
      .flatMap((r) => r.lines)
      .filter((l) => l.sale_line_id === saleLineId)
      .reduce((sum, l) => sum + Number(l.quantity), 0)

  const totalRefunded = returns.reduce((sum, r) => sum + Number(r.refund), 0)

  const canDelete = user?.role === 'owner' || user?.role === 'manager'
  const isOwnSaleWithinWindow =
    user != null &&
    user.id === sale.seller_id &&
    Date.now() - new Date(sale.created_at).getTime() < 24 * 60 * 60 * 1000
  const canEdit = canDelete || isOwnSaleWithinWindow

  async function handleSendReceipt() {
    setReceiptError(null)
    setSendingReceipt(true)
    try {
      const receipt = await getReceipt(sale.id)
      if (receipt.whatsapp_link) {
        window.open(receipt.whatsapp_link, '_blank', 'noopener,noreferrer')
      } else {
        setReceiptError('У клиента не указан телефон/WhatsApp')
      }
    } catch (err) {
      setReceiptError(err instanceof ApiError ? err.message : 'Не удалось получить квитанцию')
    } finally {
      setSendingReceipt(false)
    }
  }

  async function handleDownloadReceipt() {
    setReceiptError(null)
    setDownloadingReceipt(true)
    try {
      const blob = await getReceiptPdf(sale.id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `chek-${sale.id}.pdf`
      link.click()
      URL.revokeObjectURL(url)

      const phone = client?.whatsapp || client?.phone
      if (phone) {
        window.open(`https://wa.me/${phone.replace(/\D/g, '')}`, '_blank', 'noopener,noreferrer')
      }
    } catch (err) {
      setReceiptError(err instanceof ApiError ? err.message : 'Не удалось получить квитанцию')
    } finally {
      setDownloadingReceipt(false)
    }
  }

  async function handleShareReceipt() {
    setReceiptError(null)
    setSharingReceipt(true)
    try {
      const blob = await getReceiptPdf(sale.id)
      const file = new File([blob], `chek-${sale.id}.pdf`, { type: 'application/pdf' })
      await navigator.share({ files: [file], title: `Чек №${sale.id}` })
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setReceiptError(err instanceof ApiError ? err.message : 'Не удалось получить квитанцию')
    } finally {
      setSharingReceipt(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const items = sale.lines
      .filter((l) => Number(quantities[l.id] || 0) > 0)
      .map((l) => ({ sale_line_id: l.id, quantity: quantities[l.id] }))
    if (items.length === 0) return
    setError(null)
    setSaving(true)
    try {
      await returnSale(sale.id, { items })
      setDone(true)
      refreshCatalog(['stock']).catch(() => {})
      onUpdated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось оформить возврат')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    setError(null)
    try {
      await deleteSale(sale.id)
      refreshCatalog(['stock']).catch(() => {})
      onUpdated()
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось удалить продажу')
      setDeleting(false)
    }
  }

  if (done) {
    return (
      <Modal title={`Продажа №${sale.id}`} onClose={onDone}>
        <div className={layoutStyles.stack}>
          <div className={layoutStyles.row} style={{ gap: 8 }}>
            <IconCheck size={18} stroke={1.8} className={styles.iconAccent} />
            <p>Возврат по продаже №{sale.id} оформлен, остаток восстановлен</p>
          </div>
        </div>
      </Modal>
    )
  }

  const headerActions = (
    <>
      <IconButton
        variant="muted"
        size="lg"
        onClick={handleSendReceipt}
        disabled={sendingReceipt}
        tooltip={
          sendingReceipt
            ? 'Открываем…'
            : client?.whatsapp || client?.phone
              ? `Отправить чек клиенту${client?.name ? ` (${client.name})` : ''}`
              : 'Отправить чек текстом'
        }
        aria-label="Отправить чек в WhatsApp"
      >
        <IconBrandWhatsapp size={22} stroke={1.8} />
      </IconButton>
      <IconButton
        variant="muted"
        size="lg"
        onClick={handleDownloadReceipt}
        disabled={downloadingReceipt}
        tooltip={
          downloadingReceipt
            ? 'Готовим…'
            : client?.whatsapp || client?.phone
              ? 'Скачать чек и открыть WhatsApp'
              : 'Скачать чек (PDF)'
        }
        aria-label="Скачать чек"
      >
        <IconDownload size={22} stroke={1.8} />
      </IconButton>
      {canShareFiles && (
        <IconButton
          variant="muted"
          size="lg"
          onClick={handleShareReceipt}
          disabled={sharingReceipt}
          tooltip={sharingReceipt ? 'Готовим…' : 'Поделиться'}
          aria-label="Поделиться чеком"
        >
          <IconShare size={22} stroke={1.8} />
        </IconButton>
      )}
    </>
  )

  return (
    <Modal title={`Продажа №${sale.id}`} onClose={onDone} size="full" headerActions={headerActions}>
      <div className={layoutStyles.stack}>
      <div className={[layoutStyles.row, layoutStyles.between, layoutStyles.wrap].join(' ')} style={{ gap: 10 }}>
        {sale.deleted_at ? (
          <span className="badge danger">Удалена</span>
        ) : (
          <span />
        )}
        {!sale.deleted_at && (
          <div className={styles.saleDetailActions}>
            {canEdit && (
              <IconButton
                variant="muted"
                size="lg"
                onClick={() => setShowEdit(true)}
                tooltip="Изменить продажу"
                aria-label="Изменить продажу"
              >
                <IconPencil size={22} stroke={1.8} />
              </IconButton>
            )}
            <IconButton
              variant="muted"
              size="lg"
              onClick={() => setShowReturn(true)}
              tooltip="Оформить возврат"
              aria-label="Оформить возврат"
            >
              <IconReceiptRefund size={22} stroke={1.8} />
            </IconButton>
            {canDelete && (
              <IconButton
                variant="danger"
                size="lg"
                onClick={() => setShowDeleteConfirm(true)}
                tooltip="Удалить продажу"
                aria-label="Удалить продажу"
              >
                <IconTrash size={22} stroke={1.8} />
              </IconButton>
            )}
          </div>
        )}
      </div>

      {(receiptError || error) && <p className={layoutStyles.error}>{receiptError || error}</p>}

      <div className={styles.saleDetailMeta}>
        <div className={styles.saleDetailMetaItem}>
          <span className={layoutStyles.textMuted}>Дата и время</span>
          <span>
            {new Date(sale.created_at).toLocaleString('ru-RU', {
              day: 'numeric',
              month: 'short',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </div>
        <div className={styles.saleDetailMetaItem}>
          <span className={layoutStyles.textMuted}>Склад</span>
          <span>{warehouseName(sale.warehouse_id)}</span>
        </div>
        <div className={styles.saleDetailMetaItem}>
          <span className={layoutStyles.textMuted}>Способ оплаты</span>
          <span className={PAYMENT_BADGE_CLASS[sale.payment_method]}>
            {PAYMENT_LABELS[sale.payment_method]}
          </span>
        </div>
        <div className={styles.saleDetailMetaItem}>
          <span className={layoutStyles.textMuted}>Сотрудник</span>
          <span>{seller ? seller.name : `#${sale.seller_id}`}</span>
        </div>
        {sale.payment_method === 'cash' && (
          <>
            <div className={styles.saleDetailMetaItem}>
              <span className={layoutStyles.textMuted}>Внесено</span>
              <span>{sale.cash_received != null ? `${formatMoney(sale.cash_received)} ₽` : '—'}</span>
            </div>
            <div className={styles.saleDetailMetaItem}>
              <span className={layoutStyles.textMuted}>Сдача</span>
              <span>{sale.change != null ? `${formatMoney(sale.change)} ₽` : '—'}</span>
            </div>
          </>
        )}
        {sale.order_id != null && (
          <div className={styles.saleDetailMetaItem}>
            <span className={layoutStyles.textMuted}>Из заказа</span>
            <Link to="/orders" className="badge accent">№{sale.order_id}</Link>
          </div>
        )}
      </div>

      {client && (
        <div className={styles.saleDetailClientCard}>
          <Link to={`/clients?highlight=${client.id}`} className={styles.saleDetailClientLink}>
            <IconUsers size={16} stroke={1.8} />
            <span className={styles.saleDetailClientName}>{client.name}</span>
          </Link>
          {clientDebt && !clientDebt.is_closed && (
            <Link
              to={`/debts?highlight=${clientDebt.id}`}
              className={DEBT_STATUS_BADGE_CLASS[clientDebt.status]}
            >
              {formatMoney(clientDebt.balance)} ₽
              {clientDebt.due_date &&
                ` · до ${new Date(clientDebt.due_date).toLocaleDateString('ru-RU')}`}
              {' · '}
              {DEBT_STATUS_LABELS[clientDebt.status]}
            </Link>
          )}
          {clientDebt && clientDebt.is_closed && (
            <span className="badge accent">Долг погашен</span>
          )}
          <Link to={`/clients?highlight=${client.id}`} className={styles.saleDetailClientArrowLink}>
            <IconChevronRight size={16} stroke={1.8} className={styles.saleDetailClientArrow} />
          </Link>
        </div>
      )}

      {returns.length > 0 && (
        <p className={layoutStyles.textMuted}>
          Возвращено: {formatMoney(totalRefunded)} ₽
          {returns
            .map((r) => r.note.trim())
            .filter(Boolean)
            .map((note, i) => (
              <span key={i}> · {note}</span>
            ))}
        </p>
      )}

      <h3 className={styles.saleDetailSectionTitle}>
        Товары <span className={layoutStyles.textMuted}>· {sale.lines.length} поз.</span>
      </h3>

      <div className={styles.saleLineList}>
        {sale.lines.map((line, i) => (
          <div
            key={line.id}
            className={[styles.saleLineRow, styles.saleHistoryRowIn].join(' ')}
            style={{ '--row-delay': `${Math.min(i, 12) * 25}ms` } as CSSProperties}
          >
            <span className={styles.saleLineName}>{productName(line.product_id)}</span>
            <span className={styles.saleLineMeta}>
              {formatQuantity(line.quantity)} {unitName(products.find((p) => p.id === line.product_id)?.unit_code ?? '')}
              {' × '}
              {formatMoney(line.price)} ₽
            </span>
            <span className={styles.saleLineTotal}>{formatMoney(line.total)} ₽</span>
          </div>
        ))}
      </div>

      <div className="sale-detail-totals">
        {Number(sale.discount) > 0 && (
          <>
            <div className="sale-detail-totals-row">
              <span>Товары</span>
              <span>{formatMoney(sale.subtotal)} ₽</span>
            </div>
            <div className="sale-detail-totals-row">
              <span>{sale.order_id != null ? 'Предоплата по заказу' : 'Скидка'}</span>
              <span>−{formatMoney(sale.discount)} ₽</span>
            </div>
          </>
        )}
        <div className="sale-detail-totals-row sale-detail-totals-row-sum">
          <span>Итого</span>
          <span>{formatMoney(sale.total)} ₽</span>
        </div>
      </div>

      <SaleNoteEditor sale={sale} canEdit={canEdit} onSaved={setSale} />

      <HistoryDisclosure
        load={() => getSaleHistory(sale.id)}
        actionLabels={SALE_HISTORY_ACTION_LABELS}
        actionIcons={SALE_HISTORY_ACTION_ICONS}
        formatDetail={formatSaleHistoryDetail}
      />

      {showReturn && (
        <Modal title={`Возврат по продаже №${sale.id}`} onClose={() => setShowReturn(false)}>
          <form className={layoutStyles.form} onSubmit={handleSubmit}>
            {sale.lines.map((line) => {
              const remaining = Number(line.quantity) - alreadyReturned(line.id)
              return (
                <label className={layoutStyles.field} key={line.id}>
                  {productName(line.product_id)} (доступно к возврату: {formatQuantity(remaining)})
                  <input
                    type="text"
                    inputMode="decimal"
                    placeholder="0"
                    disabled={remaining <= 0}
                    value={quantities[line.id]}
                    onChange={(e) => {
                      const normalized = normalizeDecimalInput(e.target.value)
                      if (normalized !== null) {
                        setQuantities((prev) => ({ ...prev, [line.id]: normalized }))
                      }
                    }}
                  />
                </label>
              )
            })}
            {error && <p className={layoutStyles.error}>{error}</p>}
            <Button type="submit" disabled={saving}>
              {saving ? 'Оформление…' : 'Вернуть товар'}
            </Button>
          </form>
        </Modal>
      )}

      {showEdit && (
        <Modal title={`Изменить продажу №${sale.id}`} onClose={() => setShowEdit(false)}>
          <SaleEditForm
            sale={sale}
            clients={clients}
            onSaved={(updated) => {
              setSale(updated)
              setShowEdit(false)
              onUpdated()
            }}
          />
        </Modal>
      )}

      {showDeleteConfirm && (
        <Modal title="Удалить продажу?" onClose={() => setShowDeleteConfirm(false)}>
          <div className={layoutStyles.stack}>
            <p>
              Продажа №{sale.id} будет удалена: все проданные товары вернутся на склад
              {sale.payment_method === 'credit' && ', а связанный долг клиента будет аннулирован'}.
              Это действие нельзя отменить.
            </p>
            {error && <p className={layoutStyles.error}>{error}</p>}
            <div className={layoutStyles.row} style={{ gap: 8 }}>
              <Button variant="danger" onClick={handleDelete} disabled={deleting}>
                {deleting ? 'Удаление…' : 'Да, удалить'}
              </Button>
              <Button variant="secondary" onClick={() => setShowDeleteConfirm(false)}>
                Отмена
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
    </Modal>
  )
}

function SaleNoteEditor({
  sale,
  canEdit,
  onSaved,
}: {
  sale: Sale
  canEdit: boolean
  onSaved: (sale: Sale) => void
}) {
  const [note, setNote] = useState(sale.note)
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const saveTimerRef = useRef<number | undefined>(undefined)
  const savedTimerRef = useRef<number | undefined>(undefined)
  const noteRef = useRef(note)
  noteRef.current = note

  useEffect(
    () => () => {
      window.clearTimeout(saveTimerRef.current)
      window.clearTimeout(savedTimerRef.current)
    },
    [],
  )

  async function saveNote(value: string) {
    setStatus('saving')
    try {
      const updated = await editSale(sale.id, { client_id: sale.client_id, note: value })
      onSaved(updated)
      setStatus('saved')
      window.clearTimeout(savedTimerRef.current)
      savedTimerRef.current = window.setTimeout(() => setStatus('idle'), 2000)
    } catch {
      setStatus('error')
    }
  }

  function handleChange(value: string) {
    setNote(value)
    window.clearTimeout(saveTimerRef.current)
    saveTimerRef.current = window.setTimeout(() => saveNote(noteRef.current), 800)
  }

  return (
    <div className={styles.saleNote}>
      <div className={styles.saleNoteHeader}>
        <span className={styles.saleNoteTitle}>Заметка к продаже</span>
        <span
          className={[
            styles.saleNoteStatus,
            status === 'idle' && styles.saleNoteStatusHidden,
            status === 'error' && styles.saleNoteStatusError,
          ]
            .filter(Boolean)
            .join(' ')}
        >
          {status === 'saving' && 'Сохранение…'}
          {status === 'saved' && (
            <>
              <IconCheck size={12} stroke={1.8} /> Сохранено
            </>
          )}
          {status === 'error' && 'Не удалось сохранить'}
        </span>
      </div>
      <textarea
        className={styles.saleNoteTextarea}
        rows={2}
        value={note}
        disabled={!canEdit}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={canEdit ? 'Например: заберёт завтра, оплата через терминал…' : 'Нет заметки'}
      />
    </div>
  )
}

function SaleEditForm({
  sale,
  clients,
  onSaved,
}: {
  sale: Sale
  clients: Client[]
  onSaved: (sale: Sale) => void
}) {
  const [clientId, setClientId] = useState<number | null>(sale.client_id)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const updated = await editSale(sale.id, { client_id: clientId, note: sale.note })
      onSaved(updated)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить изменения')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={layoutStyles.form} onSubmit={handleSubmit}>
      <label className={layoutStyles.field}>
        Клиент
        <Select
          value={String(clientId ?? '')}
          onChange={(v) => setClientId(v ? Number(v) : null)}
          options={[
            { value: '', label: 'Без клиента' },
            ...clients.map((c) => ({ value: String(c.id), label: c.name })),
          ]}
        />
      </label>
      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Сохранить'}
      </Button>
    </form>
  )
}

