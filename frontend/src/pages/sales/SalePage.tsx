import { lazy, Suspense, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  listProducts,
  getByBarcode,
  listCategories,
  listUnits,
  type Product,
  type Category,
  type Unit,
} from '../../entities/product/api'
import { listWarehouses, listStock, type Warehouse, type StockItem } from '../../entities/inventory/api'
import { searchClients, createClient, type Client } from '../../entities/counterparty/api'
import { listClientDebts, type Debt } from '../../entities/debt/api'
import { listEmployees } from '../../entities/profile/api'
import type { User } from '../../entities/auth/api'
import {
  createSale,
  returnSale,
  getReceipt,
  listSales,
  editSale,
  deleteSale,
  getSaleHistory,
  listSaleReturns,
  type PaymentMethod,
  type SaleItemInput,
  type Sale,
  type SaleHistoryEntry,
} from '../../entities/sale/api'
import { ApiError } from '../../shared/api/client'
import { Icon } from '../../shared/ui/icons/Icon'
import { Modal } from '../../shared/ui/Modal'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
import { isBarcodeScannerSupported } from '../../entities/barcode/barcodeSupport'

const BarcodeScanner = lazy(() =>
  import('../../entities/barcode/BarcodeScanner').then((m) => ({ default: m.BarcodeScanner })),
)
import {
  formatQuantity,
  formatMoney,
  pluralizeSales,
  lineTotalCents,
  centsToMoney,
  normalizeDecimalInput,
} from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from '../../entities/debt/debtStatus'
import { useAuth } from '../../app/AuthContext'

const DRAFT_KEY = 'waysklad:sale-draft'

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
    const raw = localStorage.getItem(DRAFT_KEY)
    return raw ? (JSON.parse(raw) as SaleDraft) : null
  } catch {
    return null
  }
}

function saveDraft(draft: SaleDraft) {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
  } catch {
    // localStorage недоступен (приватный режим и т.п.) — черновик просто не переживёт перезагрузку
  }
}

function clearDraft() {
  localStorage.removeItem(DRAFT_KEY)
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

function isWithinPeriod(dateStr: string, period: PeriodFilter): boolean {
  if (period === 'all') return true
  const date = new Date(dateStr)
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  if (period === 'today') return date >= startOfToday
  if (period === 'week') {
    const weekAgo = new Date(startOfToday)
    weekAgo.setDate(weekAgo.getDate() - 6)
    return date >= weekAgo
  }
  const monthAgo = new Date(startOfToday)
  monthAgo.setDate(monthAgo.getDate() - 29)
  return date >= monthAgo
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
  const [sales, setSales] = useState<Sale[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showNewSale, setShowNewSale] = useState(false)
  const [hasDraft] = useState(() => loadDraft() !== null)
  const [period, setPeriod] = useState<PeriodFilter>('all')
  const [paymentFilter, setPaymentFilter] = useState<PaymentMethod | 'all'>('all')
  const [warehouseFilter, setWarehouseFilter] = useState<number | 'all'>('all')
  const [clientQuery, setClientQuery] = useState('')
  const [sortMode, setSortMode] = useState<SaleSortMode>('date_desc')
  const [selectedSale, setSelectedSale] = useState<Sale | null>(null)
  const [pinned, setPinned] = useState(false)
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

  async function load() {
    setLoading(true)
    try {
      const [s, w, c] = await Promise.all([listSales(), listWarehouses(), searchClients()])
      setSales(s)
      setWarehouses(w)
      setClients(c)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить продажи')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const warehouseName = (id: number) => warehouses.find((w) => w.id === id)?.name ?? `#${id}`
  const clientName = (id: number | null) =>
    id == null ? null : clients.find((c) => c.id === id)?.name ?? `#${id}`

  const periodSales = useMemo(() => {
    const query = clientQuery.trim().toLowerCase()
    return sales.filter(
      (s) =>
        isWithinPeriod(s.created_at, period) &&
        (warehouseFilter === 'all' || s.warehouse_id === warehouseFilter) &&
        (query === '' || (clientName(s.client_id) ?? '').toLowerCase().includes(query)),
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sales, period, warehouseFilter, clientQuery, clients])

  const filteredSales = useMemo(() => {
    const list =
      paymentFilter === 'all'
        ? periodSales
        : periodSales.filter((s) => s.payment_method === paymentFilter)
    const sorted = [...list]
    if (sortMode === 'date_asc') {
      sorted.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
    } else if (sortMode === 'payment') {
      const order: Record<PaymentMethod, number> = { cash: 0, transfer: 1, credit: 2 }
      sorted.sort((a, b) => order[a.payment_method] - order[b.payment_method])
    } else {
      sorted.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    }
    return sorted
  }, [periodSales, paymentFilter, sortMode])

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
  const periodTotalAll = periodSales.reduce((sum, s) => sum + Number(s.total), 0)
  const paymentStats = periodSales.reduce(
    (acc, s) => {
      acc[s.payment_method].total += Number(s.total)
      acc[s.payment_method].count += 1
      return acc
    },
    {
      cash: { total: 0, count: 0 },
      transfer: { total: 0, count: 0 },
      credit: { total: 0, count: 0 },
    } as Record<PaymentMethod, { total: number; count: number }>,
  )

  const activeFilterCount =
    (warehouseFilter !== 'all' ? 1 : 0) +
    (paymentFilter !== 'all' ? 1 : 0) +
    (sortMode !== 'date_desc' ? 1 : 0) +
    (clientQuery.trim() !== '' ? 1 : 0)

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
    <div className="stack">
      <div className="section-title">
        <h2>Продажи</h2>
        <Button onClick={() => setShowNewSale(true)}>
          <Icon name="plus" size={16} />
          {hasDraft ? 'Продолжить продажу' : 'Новая продажа'}
        </Button>
      </div>

      <div ref={sentinelRef} style={{ height: 1, marginBottom: -1 }} />
      <div className={`sale-filters-bar${pinned ? ' is-pinned' : ''}`}>
        <div className="sale-period-tabs">
          {(Object.keys(PERIOD_LABELS) as PeriodFilter[]).map((p) => (
            <Button
              key={p}
              translate="no"
              variant={period === p ? 'primary' : 'secondary'}
              onClick={() => setPeriod(p)}
            >
              {PERIOD_LABELS[p]}
            </Button>
          ))}
        </div>
        <div className="sale-filters-scroll">
          <input
            className={`sale-client-search${clientQuery.trim() !== '' ? ' sale-filter-active' : ''}`}
            placeholder="Клиент"
            value={clientQuery}
            onChange={(e) => setClientQuery(e.target.value)}
          />
          {warehouses.length > 1 && (
            <label className="sale-sort-field">
              <Select
                className={warehouseFilter !== 'all' ? 'sale-filter-active' : undefined}
                value={warehouseFilter === 'all' ? 'all' : String(warehouseFilter)}
                onChange={(v) => setWarehouseFilter(v === 'all' ? 'all' : Number(v))}
                options={[
                  { value: 'all', label: 'Все склады' },
                  ...warehouses.map((w) => ({ value: String(w.id), label: w.name })),
                ]}
              />
            </label>
          )}
          <label className="sale-sort-field">
            <Select
              className={sortMode !== 'date_desc' ? 'sale-filter-active' : undefined}
              value={sortMode}
              onChange={(v) => setSortMode(v as SaleSortMode)}
              options={(Object.keys(SALE_SORT_LABELS) as SaleSortMode[]).map((mode) => ({
                value: mode,
                label: SALE_SORT_LABELS[mode],
              }))}
            />
          </label>
          {activeFilterCount > 0 && (
            <Button
              className="sale-reset-link"
              onClick={() => {
                setPaymentFilter('all')
                setSortMode('date_desc')
                setWarehouseFilter('all')
                setClientQuery('')
              }}
            >
              <Icon name="close" size={12} /> Сбросить
            </Button>
          )}
        </div>
      </div>

      {!loading && filteredSales.length > 0 && (
        <div className="card card-full sale-period-summary">
          <h3 className="sale-period-summary-title">
            Итого за «{PERIOD_LABELS[period]}»
            {warehouseFilter !== 'all' && ` · ${warehouseName(warehouseFilter)}`}
            {paymentFilter !== 'all' && ` · ${PAYMENT_LABELS[paymentFilter]}`}
            {clientQuery.trim() !== '' && ` · «${clientQuery.trim()}»`}
          </h3>
          <div className="grid-stats">
            <div className="stat">
              <span className="stat-label">Выручка</span>
              <span className="stat-value">{formatMoney(periodTotal)} ₽</span>
            </div>
            <div className="stat">
              <span className="stat-label">Продаж</span>
              <span className="stat-value">{filteredSales.length}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Средний чек</span>
              <span className="stat-value">{formatMoney(avgCheck)} ₽</span>
            </div>
          </div>
          <div className="sale-payment-breakdown">
            <Button
              className={`sale-payment-item${paymentFilter === 'all' ? ' sale-payment-item-active' : ''}`}
              onClick={() => setPaymentFilter('all')}
            >
              <span className="badge sale-payment-badge-all">Все способы</span>
              <span>
                {periodSales.length} · {formatMoney(periodTotalAll)} ₽
              </span>
            </Button>
            {(Object.keys(PAYMENT_LABELS) as PaymentMethod[]).map((method) => (
              <Button
                key={method}
                className={`sale-payment-item${paymentFilter === method ? ' sale-payment-item-active' : ''}`}
                onClick={() => setPaymentFilter(method)}
                disabled={paymentStats[method].count === 0}
              >
                <span className={PAYMENT_BADGE_CLASS[method]}>{PAYMENT_LABELS[method]}</span>
                <span>
                  {paymentStats[method].count} · {formatMoney(paymentStats[method].total)} ₽
                </span>
              </Button>
            ))}
          </div>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : filteredSales.length === 0 ? (
        <p className="text-muted">
          {sales.length === 0 ? 'Продаж пока нет — начните первую' : 'За этот период продаж нет'}
        </p>
      ) : (
        <div className="stack" style={{ gap: 16 }}>
          {groups.map((group) => (
            <div className="sale-day-group" key={group.label}>
              <div className="sale-day-header">
                <span>{group.label}</span>
                <span className="sale-day-header-stats">
                  <span>
                    {group.count} {pluralizeSales(group.count)}
                  </span>
                  <span className="sale-day-header-total">{formatMoney(group.total)} ₽</span>
                </span>
              </div>
              <div className="sale-history">
                {group.sales.map((s) => (
                  <Button
                    className="sale-history-row"
                    style={{ gridTemplateColumns: historyRowColumns }}
                    key={s.id}
                    onClick={() => setSelectedSale(s)}
                  >
                    <span className="sale-history-total">{formatMoney(s.total)} ₽</span>
                    {showPaymentTag && (
                      <span className={PAYMENT_BADGE_CLASS[s.payment_method]}>
                        {PAYMENT_LABELS[s.payment_method]}
                      </span>
                    )}
                    {showWarehouseTag && (
                      <span className="sale-history-detail">
                        <Icon name="stock" size={13} />
                        {warehouseName(s.warehouse_id)}
                      </span>
                    )}
                    <span className="sale-history-detail">
                      {clientName(s.client_id) && (
                        <>
                          <Icon name="clients" size={13} />
                          {clientName(s.client_id)}
                        </>
                      )}
                    </span>
                    <span className="sale-history-time">
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
                  </Button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedSale && (
        <Modal title={`Продажа №${selectedSale.id}`} onClose={() => setSelectedSale(null)} size="full">
          <LastSaleCard
            sale={selectedSale}
            warehouses={warehouses}
            clients={clients}
            onDone={() => setSelectedSale(null)}
            onUpdated={load}
          />
        </Modal>
      )}

      {showNewSale && (
        <NewSaleForm
          onClose={() => setShowNewSale(false)}
          onDone={() => {
            setShowNewSale(false)
            load()
          }}
        />
      )}
    </div>
  )
}

function NewSaleForm({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const draft = useMemo(() => loadDraft(), [])

  const [products, setProducts] = useState<Product[]>([])
  const [productsLoading, setProductsLoading] = useState(false)
  const [categories, setCategories] = useState<Category[]>([])
  const [units, setUnits] = useState<Unit[]>([])
  const [stock, setStock] = useState<StockItem[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
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
  const [discount, setDiscount] = useState(draft?.discount ?? '0')
  const [discountMode, setDiscountMode] = useState<'amount' | 'percent'>(
    draft?.discountMode ?? 'amount',
  )
  const [clients, setClients] = useState<Client[]>([])
  const [clientId, setClientId] = useState<number | null>(draft?.clientId ?? null)
  const [showNewClientForm, setShowNewClientForm] = useState(false)
  const [showScanner, setShowScanner] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [lastSale, setLastSale] = useState<Sale | null>(null)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(timer)
  }, [query])

  useEffect(() => {
    setProductsLoading(true)
    listProducts(debouncedQuery)
      .then(setProducts)
      .catch(() => {})
      .finally(() => setProductsLoading(false))
  }, [debouncedQuery])

  useEffect(() => {
    listCategories().then(setCategories).catch(() => {})
    listUnits().then(setUnits).catch(() => {})
    listStock().then(setStock).catch(() => {})
    listWarehouses().then((list) => {
      setWarehouses(list)
      if (list.length > 0 && warehouseId == null) setWarehouseId(list[0].id)
    }).catch(() => {})
    searchClients().then(setClients).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Черновик переживает закрытие модалки/перезагрузку страницы, пока продажа не проведена
  useEffect(() => {
    if (lastSale) return
    if (cart.length === 0) {
      clearDraft()
      return
    }
    saveDraft({ warehouseId, cart, payment, discount, discountMode, clientId })
  }, [warehouseId, cart, payment, discount, discountMode, clientId, lastSale])

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
      : stock.find((s) => s.product_id === productId && s.warehouse_id === warehouseId)?.quantity ?? '0'

  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code
  const isFractional = (code: string) => units.find((u) => u.code === code)?.fractional ?? false

  const filtered = useMemo(() => {
    let list = products
    if (categoryId != null) {
      list = list.filter((p) => p.category_id === categoryId)
    }
    if (warehouseId != null && !showAllStock) {
      list = list.filter((p) => Number(stockFor(p.id) ?? 0) > 0)
    }
    const sorted = [...list]
    sorted.sort((a, b) => {
      switch (sortMode) {
        case 'price_asc':
          return Number(a.retail_price) - Number(b.retail_price)
        case 'price_desc':
          return Number(b.retail_price) - Number(a.retail_price)
        case 'stock_desc':
          return Number(stockFor(b.id) ?? 0) - Number(stockFor(a.id) ?? 0)
        default:
          return a.name.localeCompare(b.name, 'ru')
      }
    })
    return sorted
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [products, categoryId, showAllStock, sortMode, stock, warehouseId])

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

  function updateLine(productId: number, field: 'quantity' | 'price', rawValue: string) {
    const normalized = normalizeDecimalInput(rawValue)
    if (normalized === null) return
    setCart((prev) =>
      prev.map((l) => {
        if (l.product.id !== productId) return l
        let value = normalized
        if (field === 'quantity' && !isFractional(l.product.unit_code) && value.includes('.')) {
          value = value.split('.')[0] || '0'
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

  function handleClear() {
    if (cart.length > 0 && !window.confirm('Очистить чек? Набранные товары будут удалены.')) {
      return
    }
    clearDraft()
    setCart([])
    setDiscount('0')
    setDiscountMode('amount')
    setClientId(null)
    setPayment('cash')
    setDebtDueDate('')
    setError(null)
  }

  const subtotalCents = cart.reduce((sum, l) => sum + lineTotalCents(l.quantity, l.price), 0)
  const subtotal = centsToMoney(subtotalCents)
  const discountAmountCents =
    discountMode === 'percent'
      ? Math.round((subtotalCents * Number(discount || 0)) / 100)
      : Math.round(Number(discount || 0) * 100)
  const discountAmount = centsToMoney(discountAmountCents)
  const total = centsToMoney(Math.max(0, subtotalCents - discountAmountCents))

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
    try {
      const items: SaleItemInput[] = cart.map((l) => ({
        product_id: l.product.id,
        quantity: l.quantity,
        price: l.price,
      }))
      const sale = await createSale({
        warehouse_id: warehouseId,
        payment_method: payment,
        items,
        discount: discountAmount.toFixed(2),
        client_id: clientId,
        debt_due_date: payment === 'credit' ? debtDueDate : null,
      })
      clearDraft()
      setLastSale(sale)
      setCart([])
      setDiscount('0')
      setClientId(null)
      setDebtDueDate('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось провести продажу')
    } finally {
      setSaving(false)
    }
  }

  if (lastSale) {
    return (
      <Modal title="Продажа проведена" onClose={onDone} size="full">
        <LastSaleCard
          sale={lastSale}
          warehouses={warehouses}
          clients={clients}
          onDone={onDone}
          onUpdated={() => {}}
        />
      </Modal>
    )
  }

  return (
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
          <span className="modal-footer-total">
            {discountAmount > 0 && (
              <span className="modal-footer-breakdown">
                {formatMoney(subtotal)} ₽ − {formatMoney(discountAmount)} ₽ ={' '}
              </span>
            )}
            Итого: <strong>{formatMoney(total)} ₽</strong>
          </span>
        </>
      }
    >
      <div className="stack">
      <div className="sale-search-panel">
        <div className="sale-search-main">
          <div className="sale-search-row">
            <Icon name="barcode" size={18} className="sale-search-icon" />
            <input
              className="sale-search-input"
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
                className="sale-scan-button"
                onClick={() => setShowScanner(true)}
              >
                <Icon name="barcode" size={16} /> Скан
              </Button>
            )}
          </div>
        </div>

        <div className="sale-filters-row">
          {warehouses.length > 1 && (
            <label className="sale-filter-field">
              <span className="sale-filter-label">Склад</span>
              <Select
                value={String(warehouseId ?? '')}
                onChange={(v) => setWarehouseId(Number(v))}
                options={warehouses.map((w) => ({ value: String(w.id), label: w.name }))}
              />
            </label>
          )}

          {categories.length > 0 && (
            <label className="sale-filter-field">
              <span className="sale-filter-label">Категория</span>
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

          <label className="sale-filter-field">
            <span className="sale-filter-label">Сортировка</span>
            <Select
              value={sortMode}
              onChange={(v) => setSortMode(v as SortMode)}
              options={Object.entries(SORT_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </label>

          {warehouseId != null && (
            <label className="sale-checkbox">
              <input
                type="checkbox"
                checked={showAllStock}
                onChange={(e) => setShowAllStock(e.target.checked)}
              />
              Показать и то, чего нет на складе
            </label>
          )}
        </div>

        {scanError && <p className="error">{scanError}</p>}
      </div>

      <div className="sale-results-panel">
        <div className="sale-results-header">
          <span>Товары</span>
          {!productsLoading && <span className="text-muted">{filtered.length} найдено</span>}
        </div>

        {productsLoading ? (
          <p className="text-muted">Загрузка…</p>
        ) : filtered.length === 0 ? (
          <p className="text-muted">Ничего не найдено</p>
        ) : (
          <div className="product-grid" style={{ maxHeight: 280, overflowY: 'auto' }}>
            {filtered.map((p) => {
              const qty = stockFor(p.id)
              const inCartQty = cartQtyByProduct.get(p.id)
              return (
                <div
                  key={p.id}
                  role="button"
                  tabIndex={0}
                  className={`product-tile${inCartQty ? ' product-tile-in-cart' : ''}`}
                  onClick={() => addToCart(p)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      addToCart(p)
                    }
                  }}
                >
                  <span className={`product-tile-cart-badge${inCartQty ? '' : ' product-tile-cart-badge-hidden'}`}>
                    {inCartQty ? (
                      <>
                        {formatQuantity(inCartQty)} {unitName(p.unit_code)}
                        <IconButton
                          className="product-tile-remove"
                          onClick={(e) => {
                            e.stopPropagation()
                            removeLine(p.id)
                          }}
                          aria-label="Убрать из чека"
                        >
                          <Icon name="close" size={10} />
                        </IconButton>
                      </>
                    ) : (
                      ' '
                    )}
                  </span>
                  <span className="product-tile-name">{p.name}</span>
                  <span className="product-tile-price">{formatMoney(p.retail_price)} ₽</span>
                  {qty !== null && (
                    <span className="product-tile-stock">
                      Остаток: {formatQuantity(qty)} {unitName(p.unit_code)}
                    </span>
                  )}
                  {maxReachedProductId === p.id && (
                    <span className="product-tile-max-reached">Больше нет на складе</span>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {showScanner && (
        <Modal title="Сканировать штрихкод" onClose={() => setShowScanner(false)}>
          <Suspense fallback={<p className="text-muted">Загрузка сканера…</p>}>
            <BarcodeScanner onDetected={handleScan} onClose={() => setShowScanner(false)} />
          </Suspense>
        </Modal>
      )}

      {cart.length > 0 && (
        <div className="stack card card-full">
          <div className="section-title">
            <h3>Чек</h3>
            <span className="text-muted">{cart.length} поз.</span>
          </div>

          <div className="table-wrap cart-table-wrap">
            <table className="cart-table">
              <colgroup>
                <col style={{ width: '40%' }} />
                <col style={{ width: '18%' }} />
                <col style={{ width: '17%' }} />
                <col style={{ width: '17%' }} />
                <col style={{ width: '8%' }} />
              </colgroup>
              <thead>
                <tr>
                  <th>Товар</th>
                  <th>Кол-во</th>
                  <th>Цена</th>
                  <th>Сумма</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {cart.map((line) => {
                  const lineTotal = centsToMoney(lineTotalCents(line.quantity, line.price))
                  const available = stockFor(line.product.id)
                  const availableNum = available !== null ? Number(available) : null
                  const overStock = availableNum !== null && Number(line.quantity || 0) > availableNum
                  return (
                    <tr key={line.product.id}>
                      <td className="cart-table-name">
                        <div>{line.product.name}</div>
                        {availableNum !== null && (
                          <div className="cart-table-stock">
                            Остаток: {formatQuantity(availableNum)} {unitName(line.product.unit_code)}
                          </div>
                        )}
                      </td>
                      <td className="cart-table-qty-cell">
                        <div className="cart-qty-stepper">
                          <input
                            type="text"
                            inputMode="decimal"
                            className={overStock ? 'cart-input-warning' : undefined}
                            value={line.quantity}
                            onChange={(e) => updateLine(line.product.id, 'quantity', e.target.value)}
                          />
                          <div className="cart-qty-step-column">
                            <IconButton
                              variant="muted"
                              className="cart-qty-step"
                              onClick={() => stepLineQuantity(line.product.id, 1, availableNum)}
                              aria-label="Увеличить количество"
                            >
                              <Icon name="chevronRight" size={10} className="cart-qty-step-icon-up" />
                            </IconButton>
                            <IconButton
                              variant="muted"
                              className="cart-qty-step"
                              onClick={() => stepLineQuantity(line.product.id, -1, availableNum)}
                              aria-label="Уменьшить количество"
                            >
                              <Icon name="chevronRight" size={10} className="cart-qty-step-icon-down" />
                            </IconButton>
                          </div>
                        </div>
                        {overStock && availableNum !== null && (
                          <div className="cart-table-warning">
                            больше остатка ({formatQuantity(availableNum)})
                          </div>
                        )}
                        {maxReachedProductId === line.product.id && (
                          <div className="cart-table-max-reached">Больше нет на складе</div>
                        )}
                      </td>
                      <td className="cart-table-price-cell">
                        <input
                          type="text"
                          inputMode="decimal"
                          value={line.price}
                          onChange={(e) => updateLine(line.product.id, 'price', e.target.value)}
                        />
                        <span className="cart-table-price-suffix">₽</span>
                      </td>
                      <td className="cart-table-total">{formatMoney(lineTotal)} ₽</td>
                      <td>
                        <IconButton
                          onClick={() => removeLine(line.product.id)}
                          aria-label="Убрать из чека"
                        >
                          <Icon name="close" size={16} />
                        </IconButton>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="sale-checkout-grid">
            <label className="field">
              Скидка
              <div className="sale-discount-row">
                <input
                  type="text"
                  inputMode="decimal"
                  value={discount}
                  onChange={(e) => {
                    const normalized = normalizeDecimalInput(e.target.value)
                    if (normalized !== null) setDiscount(normalized)
                  }}
                />
                <div className="sale-discount-toggle">
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
                <span className="text-muted">= {formatMoney(discountAmount)} ₽</span>
              )}
            </label>

            <label className="field">
              Оплата
              <Select
                value={payment}
                onChange={(v) => setPayment(v as PaymentMethod)}
                options={Object.entries(PAYMENT_LABELS).map(([value, label]) => ({ value, label }))}
              />
            </label>

            <label className="field sale-client-field">
              Клиент
              {payment === 'credit' && (
                <span className="sale-client-required"> — обязательно для продажи в долг</span>
              )}
              <div className="sale-client-row">
                <Select
                  required={payment === 'credit'}
                  value={String(clientId ?? '')}
                  onChange={(v) => setClientId(v ? Number(v) : null)}
                  options={[
                    { value: '', label: 'Без клиента' },
                    ...clients.map((c) => ({ value: String(c.id), label: c.name })),
                  ]}
                />
                <Button variant="secondary" onClick={() => setShowNewClientForm(true)}>
                  <Icon name="plus" size={16} /> Клиент
                </Button>
              </div>
            </label>

            {payment === 'credit' && (
              <label className="field">
                Долг до
                <DateInput
                  required
                  value={debtDueDate}
                  min={new Date().toISOString().slice(0, 10)}
                  onChange={setDebtDueDate}
                />
              </label>
            )}
          </div>

          {showNewClientForm && (
            <Modal title="Новый клиент" onClose={() => setShowNewClientForm(false)}>
              <QuickNewClientForm
                onCreated={(client) => {
                  setClients((prev) => [...prev, client])
                  setClientId(client.id)
                  setShowNewClientForm(false)
                }}
              />
            </Modal>
          )}

          {error && <p className="error">{error}</p>}
        </div>
      )}
      </div>
    </Modal>
  )
}

const SALE_HISTORY_ACTION_LABELS: Record<string, string> = {
  'sale.create': 'Продажа создана',
  'sale.return': 'Оформлен возврат',
  'sale.edit': 'Изменены данные продажи',
  'sale.delete': 'Продажа удалена',
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
  const [sale, setSale] = useState(initialSale)
  const [products, setProducts] = useState<Product[]>([])
  const [units, setUnits] = useState<Unit[]>([])
  const [employees, setEmployees] = useState<User[]>([])
  const [returns, setReturns] = useState<{ sale_line_id: number; quantity: string }[]>([])
  const [clientDebt, setClientDebt] = useState<Debt | null>(null)
  const [history, setHistory] = useState<SaleHistoryEntry[] | null>(null)
  const [loadingHistory, setLoadingHistory] = useState(false)
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

  useEffect(() => {
    listProducts().then(setProducts).catch(() => {})
    listUnits().then(setUnits).catch(() => {})
    listSaleReturns(sale.id).then((list) => setReturns(list.flatMap((r) => r.lines))).catch(() => {})
    listEmployees().then(setEmployees).catch(() => {})
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
      .filter((r) => r.sale_line_id === saleLineId)
      .reduce((sum, r) => sum + Number(r.quantity), 0)

  const canDelete = user?.role === 'owner' || user?.role === 'manager'
  const isOwnSaleWithinWindow =
    user != null &&
    user.id === sale.seller_id &&
    Date.now() - new Date(sale.created_at).getTime() < 24 * 60 * 60 * 1000
  const canEdit = canDelete || isOwnSaleWithinWindow

  async function loadHistory() {
    setLoadingHistory(true)
    try {
      setHistory(await getSaleHistory(sale.id))
    } catch {
      setHistory([])
    } finally {
      setLoadingHistory(false)
    }
  }

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
      onUpdated()
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось удалить продажу')
      setDeleting(false)
    }
  }

  if (done) {
    return (
      <div className="stack">
        <div className="card card-full row" style={{ gap: 8 }}>
          <Icon name="check" size={18} className="icon-accent" />
          <p>Возврат по продаже №{sale.id} оформлен, остаток восстановлен</p>
        </div>
        <Button onClick={onDone}>
          Готово
        </Button>
      </div>
    )
  }

  return (
    <div className="stack card card-full">
      <div className="row between wrap" style={{ gap: 10 }}>
        <p>
          Продажа №{sale.id} на сумму <strong>{formatMoney(sale.total)} ₽</strong>
          {sale.deleted_at && <span className="badge danger" style={{ marginLeft: 8 }}>Удалена</span>}
        </p>
        <div className="row wrap" style={{ gap: 8 }}>
          <Button
            variant="secondary"
            onClick={handleSendReceipt}
            disabled={sendingReceipt}
          >
            {sendingReceipt ? 'Открываем…' : 'В WhatsApp'}
          </Button>
          {!sale.deleted_at && (
            <Button variant="danger" onClick={() => setShowReturn(true)}>
              Оформить возврат
            </Button>
          )}
          {!sale.deleted_at && canEdit && (
            <Button variant="secondary" onClick={() => setShowEdit(true)}>
              Изменить
            </Button>
          )}
          {!sale.deleted_at && canDelete && (
            <Button variant="danger" onClick={() => setShowDeleteConfirm(true)}>
              Удалить продажу
            </Button>
          )}
        </div>
      </div>

      {receiptError && <p className="error">{receiptError}</p>}
      {error && <p className="error">{error}</p>}

      <div className="sale-detail-meta">
        <div className="sale-detail-meta-item">
          <span className="text-muted">Дата и время</span>
          <span>
            {new Date(sale.created_at).toLocaleString('ru-RU', {
              day: 'numeric',
              month: 'long',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </div>
        <div className="sale-detail-meta-item">
          <span className="text-muted">Склад</span>
          <span>{warehouseName(sale.warehouse_id)}</span>
        </div>
        <div className="sale-detail-meta-item">
          <span className="text-muted">Способ оплаты</span>
          <span className={PAYMENT_BADGE_CLASS[sale.payment_method]}>
            {PAYMENT_LABELS[sale.payment_method]}
          </span>
        </div>
        <div className="sale-detail-meta-item">
          <span className="text-muted">Сотрудник</span>
          <span>{seller ? seller.name : `#${sale.seller_id}`}</span>
        </div>
      </div>

      {client && (
        <Link
          to={`/clients?highlight=${client.id}`}
          className="sale-detail-client-card"
        >
          <Icon name="clients" size={16} />
          <span className="sale-detail-client-name">{client.name}</span>
          {clientDebt && !clientDebt.is_closed && (
            <span className={DEBT_STATUS_BADGE_CLASS[clientDebt.status]}>
              {formatMoney(clientDebt.balance)} ₽
              {clientDebt.due_date &&
                ` · до ${new Date(clientDebt.due_date).toLocaleDateString('ru-RU')}`}
              {' · '}
              {DEBT_STATUS_LABELS[clientDebt.status]}
            </span>
          )}
          {clientDebt && clientDebt.is_closed && <span className="badge accent">Долг погашен</span>}
          <Icon name="chevronRight" size={16} className="sale-detail-client-arrow" />
        </Link>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Товар</th>
              <th>Кол-во</th>
              <th>Цена</th>
              <th>Сумма</th>
            </tr>
          </thead>
          <tbody>
            {sale.lines.map((line) => (
              <tr key={line.id}>
                <td>{productName(line.product_id)}</td>
                <td>
                  {formatQuantity(line.quantity)} {unitName(products.find((p) => p.id === line.product_id)?.unit_code ?? '')}
                </td>
                <td>{formatMoney(line.price)} ₽</td>
                <td>{formatMoney(line.total)} ₽</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SaleNoteEditor sale={sale} canEdit={canEdit} onSaved={setSale} />

      <div className="sale-detail-history">
        {history === null ? (
          <Button variant="secondary" onClick={loadHistory} disabled={loadingHistory}>
            {loadingHistory ? 'Загрузка…' : 'Показать историю изменений'}
          </Button>
        ) : history.length === 0 ? (
          <p className="text-muted">Изменений не было</p>
        ) : (
          <div className="stack" style={{ gap: 6 }}>
            <span className="text-muted">История изменений</span>
            {history.map((entry) => (
              <div key={entry.id} className="sale-detail-history-item">
                <span>{SALE_HISTORY_ACTION_LABELS[entry.action] ?? entry.action}</span>
                <span className="text-muted">
                  {new Date(entry.created_at).toLocaleString('ru-RU', {
                    day: 'numeric',
                    month: 'short',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {showReturn && (
        <Modal title={`Возврат по продаже №${sale.id}`} onClose={() => setShowReturn(false)}>
          <form className="form" onSubmit={handleSubmit}>
            {sale.lines.map((line) => {
              const remaining = Number(line.quantity) - alreadyReturned(line.id)
              return (
                <label className="field" key={line.id}>
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
            {error && <p className="error">{error}</p>}
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
          <div className="stack">
            <p>
              Продажа №{sale.id} будет удалена: все проданные товары вернутся на склад
              {sale.payment_method === 'credit' && ', а связанный долг клиента будет аннулирован'}.
              Это действие нельзя отменить.
            </p>
            {error && <p className="error">{error}</p>}
            <div className="row" style={{ gap: 8 }}>
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

      <Button onClick={onDone}>
        Готово
      </Button>
    </div>
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
    <div className="sale-note">
      <div className="sale-note-header">
        <span className="sale-note-title">Заметка к продаже</span>
        <span
          className={`sale-note-status${status === 'idle' ? ' sale-note-status-hidden' : ''}${status === 'error' ? ' sale-note-status-error' : ''}`}
        >
          {status === 'saving' && 'Сохранение…'}
          {status === 'saved' && (
            <>
              <Icon name="check" size={12} /> Сохранено
            </>
          )}
          {status === 'error' && 'Не удалось сохранить'}
        </span>
      </div>
      <textarea
        className="sale-note-textarea"
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
    <form className="form" onSubmit={handleSubmit}>
      <label className="field">
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
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Сохранить'}
      </Button>
    </form>
  )
}

function QuickNewClientForm({ onCreated }: { onCreated: (client: Client) => void }) {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const client = await createClient({ name, phone })
      onCreated(client)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось добавить клиента')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="field">
        Имя
        <input value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
      </label>
      <label className="field">
        Телефон
        <input value={phone} onChange={(e) => setPhone(e.target.value)} />
      </label>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving || !name.trim()}>
        {saving ? 'Сохранение…' : 'Добавить и выбрать'}
      </Button>
    </form>
  )
}
