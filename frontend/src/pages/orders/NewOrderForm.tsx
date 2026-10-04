import { lazy, Suspense, useMemo, useState, type FormEvent } from 'react'
import {
  createOrder,
  updateOrder,
  type Order,
  type OrderSource,
  type OrderFormInput,
} from '../../entities/order/api'
import { getByBarcode, type Product, type Unit } from '../../entities/product/api'
import type { Client } from '../../entities/counterparty/api'
import type { Warehouse, StockItem } from '../../entities/inventory/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import {
  IconTrash,
  IconBarcode,
  IconChevronRight,
  IconSearch,
} from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { StockWarningIcon } from '../../shared/ui/StockWarningIcon'
import { InfoHint } from '../../shared/ui/InfoHint'
import {
  formatMoney,
  formatQuantity,
  normalizeDecimalInput,
  isOutOfStock,
  isLowStock,
} from '../../shared/lib/format'
import { isBarcodeScannerSupported } from '../../entities/barcode/barcodeSupport'
import { ORDER_SOURCE_LABELS } from './orderLabels'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './OrdersPage.module.css'

const BarcodeScanner = lazy(() =>
  import('../../entities/barcode/BarcodeScanner').then((m) => ({ default: m.BarcodeScanner })),
)

interface OrderFormLine {
  product: Product
  quantity: string
  price: string
}

export function NewOrderForm({
  products,
  units,
  clients,
  warehouses,
  stock,
  editOrder,
  onDone,
}: {
  products: Product[]
  units: Unit[]
  clients: Client[]
  warehouses: Warehouse[]
  stock: StockItem[]
  editOrder?: Order
  onDone: (order: Order) => void
}) {
  const [clientId, setClientId] = useState<number | null>(editOrder?.client_id ?? clients[0]?.id ?? null)
  const [warehouseId, setWarehouseId] = useState<number | null>(editOrder?.warehouse_id ?? warehouses[0]?.id ?? null)
  const [source, setSource] = useState<OrderSource>(editOrder?.source ?? 'in_person')
  const [lines, setLines] = useState<OrderFormLine[]>(() =>
    (editOrder?.lines ?? [])
      .map((l) => {
        const product = products.find((p) => p.id === l.product_id)
        return product ? { product, quantity: l.quantity, price: l.price } : null
      })
      .filter((l): l is OrderFormLine => l !== null),
  )
  const [query, setQuery] = useState('')
  const [dueDate, setDueDate] = useState(editOrder?.due_date ?? '')
  const [prepayment, setPrepayment] = useState(editOrder?.prepayment ?? '0')
  const [note, setNote] = useState(editOrder?.note ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [showScanner, setShowScanner] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)

  const isFractional = (code: string) => units.find((u) => u.code === code)?.fractional ?? false
  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code

  const stockFor = (productId: number) =>
    warehouseId == null
      ? null
      : stock.find((s) => s.product_id === productId && s.warehouse_id === warehouseId)?.available ?? null
  const reservedFor = (productId: number) =>
    warehouseId == null
      ? 0
      : Number(stock.find((s) => s.product_id === productId && s.warehouse_id === warehouseId)?.reserved ?? '0')

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return products
    return products.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.sku.toLowerCase().includes(q) ||
        (p.barcode ?? '').toLowerCase().includes(q),
    )
  }, [products, query])

  function addLine(product: Product) {
    setLines((prev) => {
      const existing = prev.find((l) => l.product.id === product.id)
      if (existing) {
        return prev.map((l) =>
          l.product.id === product.id ? { ...l, quantity: String(Number(l.quantity) + 1) } : l,
        )
      }
      return [...prev, { product, quantity: '1', price: String(Number(product.retail_price)) }]
    })
  }

  function updateLine(productId: number, field: 'quantity' | 'price', rawValue: string) {
    const normalized = normalizeDecimalInput(rawValue)
    if (normalized === null) return
    setLines((prev) =>
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

  function stepLineQuantity(productId: number, delta: number) {
    setLines((prev) =>
      prev.map((l) => {
        if (l.product.id !== productId) return l
        const next = Math.max(0, Number(l.quantity || 0) + delta)
        const quantity = isFractional(l.product.unit_code)
          ? (Number.isInteger(next) ? next.toFixed(1) : String(next))
          : String(Math.round(next))
        return { ...l, quantity }
      }),
    )
  }

  function removeLine(productId: number) {
    setLines((prev) => prev.filter((l) => l.product.id !== productId))
  }

  async function handleScan(code: string) {
    setShowScanner(false)
    setScanError(null)
    try {
      const product = await getByBarcode(code)
      if (product) {
        addLine(product)
      } else {
        setScanError(`Товар со штрихкодом ${code} не найден`)
      }
    } catch {
      setScanError('Не удалось найти товар по штрихкоду')
    }
  }

  const total = lines.reduce((sum, l) => sum + Number(l.quantity || 0) * Number(l.price || 0), 0)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!clientId || !warehouseId || !dueDate || lines.length === 0) return
    setError(null)
    setSaving(true)
    try {
      const input: OrderFormInput = {
        client_id: clientId,
        warehouse_id: warehouseId,
        items: lines.map((l) => ({
          product_id: l.product.id,
          quantity: l.quantity,
          price: l.price,
        })),
        due_date: dueDate,
        prepayment,
        source,
        note,
      }
      const order = editOrder ? await updateOrder(editOrder.id, input) : await createOrder(input)
      onDone(order)
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : `Не удалось ${editOrder ? 'сохранить' : 'создать'} заказ`,
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={layoutStyles.form} onSubmit={handleSubmit}>
      <div className={layoutStyles.row}>
        <label className={layoutStyles.field} style={{ flex: 1, minWidth: 0 }}>
          Клиент
          <Select
            value={clientId != null ? String(clientId) : ''}
            onChange={(v) => setClientId(Number(v))}
            options={clients.map((c) => ({ value: String(c.id), label: c.name }))}
            placeholder={clients.length ? 'Выберите клиента' : 'Клиентов пока нет'}
          />
        </label>
        {warehouses.length > 1 && (
          <label className={layoutStyles.field} style={{ flex: 1, minWidth: 0 }}>
            Склад
            <Select
              value={warehouseId != null ? String(warehouseId) : ''}
              onChange={(v) => setWarehouseId(Number(v))}
              options={warehouses.map((w) => ({ value: String(w.id), label: w.name }))}
            />
          </label>
        )}
        <label className={layoutStyles.field} style={{ flex: 1, minWidth: 0 }}>
          Источник
          <Select
            value={source}
            onChange={(v) => setSource(v as OrderSource)}
            options={Object.entries(ORDER_SOURCE_LABELS)
              .filter(([value]) => value !== 'storefront')
              .map(([value, label]) => ({ value, label }))}
          />
        </label>
      </div>

      <div className={layoutStyles.stack} style={{ gap: 10 }}>
        <div className="sale-search-row">
          <IconSearch size={16} stroke={1.8} className="sale-search-icon" />
          <input
            className="sale-search-input"
            placeholder="Поиск по названию, артикулу, штрихкоду…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {isBarcodeScannerSupported() && (
            <Button type="button" variant="secondary" onClick={() => setShowScanner(true)}>
              <IconBarcode size={16} stroke={1.8} />
            </Button>
          )}
        </div>
        {scanError && <p className={layoutStyles.error}>{scanError}</p>}
        <div className="sale-results-header">
          <span>Товары</span>
          <span className={layoutStyles.textMuted}>{filtered.length} найдено</span>
        </div>
        {filtered.length === 0 ? (
          <p className={layoutStyles.textMuted}>Ничего не найдено</p>
        ) : (
          <div className={layoutStyles.productGrid}>
            {filtered.map((p) => {
              const inLineQty = lines.find((l) => l.product.id === p.id)?.quantity
              const available = stockFor(p.id)
              const reserved = reservedFor(p.id)
              return (
                <div
                  key={p.id}
                  role="button"
                  tabIndex={0}
                  className={[layoutStyles.productTile, inLineQty ? layoutStyles.productTileInCart : null]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => addLine(p)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      addLine(p)
                    }
                  }}
                >
                  <ProductPhoto src={p.photo} />
                  <div className={layoutStyles.productTileBody}>
                    <span className={layoutStyles.productTileName}>{p.name}</span>
                    <span className={layoutStyles.productTilePriceLabel}>Цена за {unitName(p.unit_code)}:</span>
                    <span className={layoutStyles.productTilePrice}>{formatMoney(p.retail_price)} ₽</span>
                    {available !== null && (
                      <span
                        className={[
                          layoutStyles.productTileStock,
                          isOutOfStock(available) ? layoutStyles.productTileStockOut : layoutStyles.productTileStockIn,
                        ].join(' ')}
                      >
                        <span className={layoutStyles.productTileStockLabel}>
                          Доступно:
                          {reserved > 0 && (
                            <InfoHint
                              text={`${formatQuantity(String(reserved))} ${unitName(p.unit_code)} зарезервировано под другие заказы и недоступно для нового — освободится, когда те заказы выдадут или отменят.`}
                            />
                          )}
                        </span>
                        <span className={layoutStyles.productTileStockValueWrap}>
                          <span className={layoutStyles.productTileStockValue}>
                            {formatQuantity(available)} {unitName(p.unit_code)}
                          </span>
                          {isLowStock(available, p.min_stock) && <StockWarningIcon />}
                        </span>
                      </span>
                    )}
                  </div>
                  <span
                    className={[
                      layoutStyles.productTileCartBadge,
                      inLineQty ? null : layoutStyles.productTileCartBadgeHidden,
                    ]
                      .filter(Boolean)
                      .join(' ')}
                  >
                    {inLineQty ? (
                      <>
                        {formatQuantity(inLineQty)}
                        <IconButton
                          className={layoutStyles.productTileRemove}
                          onClick={(e) => {
                            e.stopPropagation()
                            removeLine(p.id)
                          }}
                          aria-label="Убрать из списка"
                        >
                          <IconTrash size={10} stroke={1.8} />
                        </IconButton>
                      </>
                    ) : (
                      ' '
                    )}
                  </span>
                </div>
              )
            })}
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

      {lines.length > 0 && (
        <div className={[layoutStyles.stack, layoutStyles.card, layoutStyles.cardFull].join(' ')}>
          <div className={layoutStyles.sectionTitle}>
            <h3>Позиции заказа</h3>
            <span className={layoutStyles.textMuted}>{lines.length} поз.</span>
          </div>
          <div className={[layoutStyles.tableWrap, styles.cartTableWrap, styles.cartTableWrapCompact].join(' ')}>
            <div className={styles.cartTableHead} style={{ gridTemplateColumns: '34% 27% 27% 12%' }}>
              <span>Товар</span>
              <span>Кол-во</span>
              <span>Цена</span>
              <span />
            </div>
            <div>
              {lines.map((line) => {
                const available = stockFor(line.product.id)
                const overStock = available !== null && Number(line.quantity || 0) > Number(available)
                return (
                  <div
                    key={line.product.id}
                    className={styles.cartTableRow}
                    style={{ gridTemplateColumns: '34% 27% 27% 12%' }}
                  >
                    <div className={styles.cartTableName}>
                      <div>{line.product.name}</div>
                      {available !== null && (
                        <div className={styles.cartTableStock}>
                          Доступно: {formatQuantity(available)} {unitName(line.product.unit_code)}
                        </div>
                      )}
                    </div>
                    <div className={styles.cartTableQtyCell}>
                      <div className={styles.cartQtyStepper}>
                        <input
                          type="text"
                          inputMode="decimal"
                          className={overStock ? styles.cartInputWarning : undefined}
                          value={line.quantity}
                          onChange={(e) => updateLine(line.product.id, 'quantity', e.target.value)}
                        />
                        <div className={styles.cartQtyStepColumn}>
                          <IconButton
                            variant="muted"
                            className={styles.cartQtyStep}
                            onClick={() => stepLineQuantity(line.product.id, 1)}
                            aria-label="Увеличить количество"
                          >
                            <IconChevronRight size={10} stroke={1.8} className={styles.cartQtyStepIconUp} />
                          </IconButton>
                          <IconButton
                            variant="muted"
                            className={styles.cartQtyStep}
                            onClick={() => stepLineQuantity(line.product.id, -1)}
                            aria-label="Уменьшить количество"
                          >
                            <IconChevronRight size={10} stroke={1.8} className={styles.cartQtyStepIconDown} />
                          </IconButton>
                        </div>
                      </div>
                      {overStock && available !== null && (
                        <div className={styles.cartTableWarning}>больше доступного ({formatQuantity(available)})</div>
                      )}
                    </div>
                    <div className={styles.cartTablePriceCell}>
                      <input
                        type="text"
                        inputMode="decimal"
                        value={line.price}
                        onChange={(e) => updateLine(line.product.id, 'price', e.target.value)}
                      />
                      <span className={styles.cartTablePriceSuffix}>₽</span>
                    </div>
                    <IconButton
                      variant="danger"
                      onClick={() => removeLine(line.product.id)}
                      aria-label="Убрать позицию"
                    >
                      <IconTrash size={16} stroke={1.8} />
                    </IconButton>
                  </div>
                )
              })}
            </div>
          </div>
          <div className={[layoutStyles.row, layoutStyles.between].join(' ')}>
            <span className={layoutStyles.textMuted}>Итого</span>
            <strong>{formatMoney(total)} ₽</strong>
          </div>
        </div>
      )}

      <div className={layoutStyles.row}>
        <label className={layoutStyles.field} style={{ flex: 1, minWidth: 0 }}>
          Дата готовности
          <DateInput required value={dueDate} onChange={setDueDate} />
        </label>
        <label className={layoutStyles.field} style={{ flex: 1, minWidth: 0 }}>
          Предоплата
          <input
            type="text"
            inputMode="decimal"
            value={prepayment}
            onChange={(e) => {
              const normalized = normalizeDecimalInput(e.target.value)
              if (normalized !== null) setPrepayment(normalized)
            }}
          />
        </label>
      </div>
      <label className={layoutStyles.field}>
        Заметка
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="из директа, размер, пожелания…" />
      </label>
      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button type="submit" disabled={saving || !clientId || !warehouseId || !dueDate || lines.length === 0}>
        {saving ? 'Сохранение…' : editOrder ? 'Сохранить изменения' : 'Создать заказ'}
      </Button>
    </form>
  )
}
