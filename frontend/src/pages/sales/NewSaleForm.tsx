import {
  lazy,
  Suspense,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { listProducts, getByBarcode, type Product } from '../../entities/product/api'
import { type Client, createClient } from '../../entities/counterparty/api'
import { useCatalog } from '../../app/CatalogContext'
import {
  createSale,
  type PaymentMethod,
  type SaleItemInput,
  type Sale,
} from '../../entities/sale/api'
import {
  IconPlus,
  IconMinus,
  IconX,
  IconBarcode,
} from '@tabler/icons-react'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Select } from '../../shared/ui/Select'
import { CreatableSelect } from '../../shared/ui/CreatableSelect'
import { DateInput } from '../../shared/ui/DateInput'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { StockWarningIcon } from '../../shared/ui/StockWarningIcon'
import { InfoHint } from '../../shared/ui/InfoHint'
import { isBarcodeScannerSupported } from '../../entities/barcode/barcodeSupport'
import { queueSale } from '../../shared/offline/outbox'
import {
  formatQuantity,
  formatMoney,
  lineTotalCents,
  centsToMoney,
  normalizeDecimalInput,
  isLowStock,
  isOutOfStock,
} from '../../shared/lib/format'
import { loadDraft, saveDraft, clearDraft, PAYMENT_LABELS, type CartLine } from './saleDraft'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './SalePage.module.css'

const BarcodeScanner = lazy(() =>
  import('../../entities/barcode/BarcodeScanner').then((m) => ({ default: m.BarcodeScanner })),
)

const PRODUCTS_PAGE_SIZE = 32

type SortMode = 'name' | 'price_asc' | 'price_desc' | 'stock_desc'

const SORT_LABELS: Record<SortMode, string> = {
  name: 'По названию',
  price_asc: 'Цена: сначала дешёвые',
  price_desc: 'Цена: сначала дорогие',
  stock_desc: 'По остатку',
}

export function NewSaleForm({
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
  const [keepChange, setKeepChange] = useState(false)
  const [discount, setDiscount] = useState(draft?.discount ?? '0')
  const [discountMode, setDiscountMode] = useState<'amount' | 'percent'>(
    draft?.discountMode ?? 'amount',
  )
  const clients = initialClients
  const [clientId, setClientId] = useState<number | null>(draft?.clientId ?? null)
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

  // Фильтр наличия и сортировка по остатку — на сервере по выбранному складу.
  useEffect(() => {
    setProductsLoading(true)
    setProducts([])
    listProducts({
      query: debouncedQuery,
      categoryId,
      sort: sortMode,
      inStockOnly: warehouseId != null && !showAllStock,
      warehouseId,
      limit: PRODUCTS_PAGE_SIZE,
      offset: 0,
    })
      .then(({ items, total }) => {
        setProducts(items)
        setProductsTotal(total)
      })
      .catch(() => {})
      .finally(() => setProductsLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQuery, categoryId, sortMode, warehouseId, showAllStock])

  function loadMoreProducts() {
    if (productsLoadingMore || products.length >= productsTotal) return
    setProductsLoadingMore(true)
    listProducts({
      query: debouncedQuery,
      categoryId,
      sort: sortMode,
      inStockOnly: warehouseId != null && !showAllStock,
      warehouseId,
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
  }, [products.length, productsTotal, productsLoadingMore, debouncedQuery, categoryId, sortMode, warehouseId, showAllStock])

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
    // Наличие и stock_desc уже на сервере (с учётом warehouse_id / in_stock_only).
    return products
  }, [products])

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
  const rawChangeCents = cashReceivedCents - totalCents
  const changeKeptCents = keepChange && rawChangeCents > 0 ? rawChangeCents : 0
  const changeCents = rawChangeCents - changeKeptCents
  const change = centsToMoney(Math.max(0, changeCents))
  const changeKept = centsToMoney(changeKeptCents)

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
    const changeKeptValue =
      cashReceivedValue && changeKeptCents > 0 ? centsToMoney(changeKeptCents) : null
    try {
      const sale = await createSale({
        warehouse_id: warehouseId,
        payment_method: payment,
        items,
        discount: discountAmount.toFixed(2),
        client_id: clientId,
        cash_received: cashReceivedValue,
        change_kept: changeKeptValue,
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
          change_kept: changeKeptValue,
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

  const checkoutActions = (
    <>
      <div className={styles.salePageActionsTotal}>
        {discountAmount > 0 && (
          <span className={styles.modalFooterBreakdown}>
            {formatMoney(subtotal)} ₽ − {formatMoney(discountAmount)} ₽
          </span>
        )}
        <span className={styles.modalFooterTotalLabel}>Итого</span>
        <strong className={styles.modalFooterTotalAmount}>
          {formatMoney(total)}
          <span className={styles.modalFooterTotalCurrency}>₽</span>
        </strong>
      </div>
      <div className={styles.salePageActionsButtons}>
        <Button variant="secondary" onClick={handleClear} disabled={cart.length === 0}>
          Очистить
        </Button>
        <Button
          className={styles.salePageActionsSubmit}
          onClick={handleCheckout}
          disabled={saving || !warehouseId || cart.length === 0}
        >
          {saving ? 'Проведение…' : 'Провести продажу'}
        </Button>
      </div>
    </>
  )

  if (offlineQueued) {
    return (
      <div className={layoutStyles.stack} style={{ textAlign: 'center', padding: '24px 12px' }}>
        <h2 style={{ margin: 0 }}>Продажа сохранена локально</h2>
        <p>
          Нет подключения к интернету. Продажа на сумму {formatMoney(offlineQueued.total)} (позиций в чеке:{' '}
          {offlineQueued.itemsCount}) сохранена на устройстве и отправится на сервер автоматически, как
          только появится сеть.
        </p>
        <Button onClick={onClose} style={{ alignSelf: 'center' }}>Понятно</Button>
      </div>
    )
  }

  return (
    <>
      <div className={layoutStyles.stack}>
        <div className={layoutStyles.sectionTitle}>
          <h2>Новая продажа</h2>
        </div>
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
                  <div className={styles.cartRowHead}>
                    <div className={styles.cartRowName}>
                      <div className={styles.cartRowTitle}>{line.product.name}</div>
                      {availableNum !== null && (
                        <div className={styles.cartTableStock}>
                          Остаток: {formatQuantity(availableNum)} {unitName(line.product.unit_code)}
                        </div>
                      )}
                    </div>
                    <button
                      type="button"
                      className={styles.cartRemoveBtn}
                      onClick={() => removeLine(line.product.id)}
                      aria-label="Убрать из чека"
                    >
                      <IconX size={16} stroke={2} />
                    </button>
                  </div>

                  <div className={styles.cartRowFields}>
                    <div className={styles.cartQtyPriceGroup}>
                      <div
                        className={[
                          styles.cartQtyStepper,
                          overStock && styles.cartQtyStepperWarn,
                        ]
                          .filter(Boolean)
                          .join(' ')}
                      >
                        <button
                          type="button"
                          className={styles.cartQtyStep}
                          onClick={() => stepLineQuantity(line.product.id, -1, availableNum)}
                          aria-label="Уменьшить количество"
                        >
                          <IconMinus size={16} stroke={2.2} />
                        </button>
                        <input
                          type="text"
                          inputMode="decimal"
                          aria-label="Количество"
                          value={line.quantity}
                          onChange={(e) =>
                            updateLine(line.product.id, 'quantity', e.target.value, availableNum)
                          }
                        />
                        <button
                          type="button"
                          className={styles.cartQtyStep}
                          onClick={() => stepLineQuantity(line.product.id, 1, availableNum)}
                          aria-label="Увеличить количество"
                        >
                          <IconPlus size={16} stroke={2.2} />
                        </button>
                      </div>

                      <div className={styles.cartPriceInputWrap}>
                        <input
                          type="text"
                          inputMode="decimal"
                          className={styles.cartPriceInput}
                          aria-label="Цена за штуку"
                          value={line.price}
                          onChange={(e) => updateLine(line.product.id, 'price', e.target.value)}
                        />
                        <span className={styles.cartTablePriceSuffix}>₽</span>
                      </div>
                    </div>

                    <div className={styles.cartLineTotal} aria-label="Сумма строки">
                      <span className={styles.cartLineTotalValue}>{formatMoney(lineTotal)}</span>
                      <span className={styles.cartLineTotalCurrency}>₽</span>
                    </div>

                    {overStock && availableNum !== null && (
                      <div className={styles.cartTableWarning}>
                        больше остатка ({formatQuantity(availableNum)})
                      </div>
                    )}
                    {maxReachedProductId === line.product.id && (
                      <div className={styles.cartTableMaxReached}>Больше нет на складе</div>
                    )}
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
                      if (normalized !== null) {
                        setCashReceived(normalized)
                        setKeepChange(false)
                      }
                    }}
                  />
                  {cashReceivedCents > 0 && (
                    <span className={changeCents < 0 && !keepChange ? styles.saleChangeShort : layoutStyles.textMuted}>
                      {rawChangeCents < 0
                        ? `Не хватает: ${formatMoney(centsToMoney(-rawChangeCents))} ₽`
                        : keepChange
                          ? `Сдача не выдана · осталось в кассе ${formatMoney(changeKept)} ₽`
                          : `Сдача: ${formatMoney(change)} ₽`}
                    </span>
                  )}
                  {rawChangeCents > 0 && (
                    <label className={styles.keepChangeRow}>
                      <input
                        type="checkbox"
                        checked={keepChange}
                        onChange={(e) => setKeepChange(e.target.checked)}
                      />
                      Клиент не взял сдачу
                    </label>
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
              <CreatableSelect
                required={payment === 'credit'}
                value={String(clientId ?? '')}
                onChange={(v) => setClientId(v ? Number(v) : null)}
                options={[
                  { value: '', label: 'Без клиента' },
                  ...clients.map((c) => ({ value: String(c.id), label: c.name })),
                ]}
                searchPlaceholder="Клиент или новый…"
                createLabel={(q) => `Создать «${q}»`}
                aria-label="Клиент"
                onCreate={async (name) => {
                  const client = await createClient({ name })
                  onClientsChange([...clients, client])
                  setClientId(client.id)
                }}
              />
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
      <div className={styles.salePageActions}>
        {checkoutActions}
      </div>
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

