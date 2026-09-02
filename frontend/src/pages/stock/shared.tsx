import { lazy, Suspense, useEffect, useMemo, useState, type FormEvent } from 'react'
import {
  createWarehouse,
  receiveGoods,
  writeOff,
  transferStock,
  type StockItem,
  type Warehouse,
} from '../../entities/inventory/api'
import { getByBarcode, type Category, type Product, type Unit } from '../../entities/product/api'
import type { User } from '../../entities/auth/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { useCatalog } from '../../app/CatalogContext'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Select } from '../../shared/ui/Select'
import { Modal } from '../../shared/ui/Modal'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { InfoHint } from '../../shared/ui/InfoHint'
import { DateInput } from '../../shared/ui/DateInput'
import { normalizeDecimalInput, formatQuantity } from '../../shared/lib/format'
import { isBarcodeScannerSupported } from '../../entities/barcode/barcodeSupport'
import {
  IconBarcode,
  IconTrash,
  IconChevronRight,
  IconArrowBarToDown,
  IconArrowBarUp,
  IconArrowsRightLeft,
  IconSearch,
  type Icon,
} from '@tabler/icons-react'
import layoutStyles from '../../shared/ui/Layout.module.css'

const BarcodeScanner = lazy(() =>
  import('../../entities/barcode/BarcodeScanner').then((m) => ({ default: m.BarcodeScanner })),
)

export type MovementMode = 'receive' | 'write_off' | 'transfer'

export const MODE_LABELS: Record<MovementMode, string> = {
  receive: 'Приёмка',
  write_off: 'Списание',
  transfer: 'Перемещение',
}

export const MODE_ICONS: Record<MovementMode, Icon> = {
  receive: IconArrowBarToDown,
  write_off: IconArrowBarUp,
  transfer: IconArrowsRightLeft,
}

/** Ответственным за склад может быть только владелец или кладовщик (storekeeper) — так же проверяется на бэкенде. */
export function useWarehouseManagerCandidates(): User[] {
  const { user } = useAuth()
  const { employees, ensureEmployees } = useCatalog()

  useEffect(() => {
    ensureEmployees().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return useMemo(() => {
    const list = employees.filter((e) => e.role === 'storekeeper' || e.role === 'owner')
    if (user && user.role === 'owner' && !list.some((e) => e.id === user.id)) {
      return [user, ...list]
    }
    return list
  }, [employees, user])
}

export function AssignedUsersField({
  candidates,
  selectedIds,
  onChange,
}: {
  candidates: User[]
  selectedIds: number[]
  onChange: (ids: number[]) => void
}) {
  function toggle(id: number) {
    onChange(
      selectedIds.includes(id) ? selectedIds.filter((v) => v !== id) : [...selectedIds, id],
    )
  }

  if (candidates.length === 0) {
    return (
      <p className={layoutStyles.textMuted}>
        Нет доступных ответственных — сначала добавьте кладовщика в «Профиль → Аккаунт → Сотрудники».
      </p>
    )
  }

  return (
    <div className={layoutStyles.stack} style={{ gap: 8 }}>
      {candidates.map((c) => (
        <label key={c.id} className={layoutStyles.row} style={{ gap: 8 }}>
          <input
            type="checkbox"
            checked={selectedIds.includes(c.id)}
            onChange={() => toggle(c.id)}
          />
          {c.name}
          {c.role === 'owner' && <span className={layoutStyles.textMuted}> (владелец)</span>}
        </label>
      ))}
    </div>
  )
}

export function NewWarehouseForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await createWarehouse({ name, address })
      onCreated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать склад')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={layoutStyles.form} onSubmit={handleSubmit}>
      <label className={layoutStyles.field}>
        Название склада
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Например, Склад на Кадырова"
          autoFocus
          required
        />
      </label>
      <label className={layoutStyles.field}>
        Адрес
        <input value={address} onChange={(e) => setAddress(e.target.value)} />
      </label>
      <p className={layoutStyles.textMuted}>
        Ответственных сотрудников можно назначить позже — на странице склада или в карточке сотрудника.
      </p>
      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Создать склад'}
      </Button>
    </form>
  )
}

export interface MovementLine {
  product: Product
  quantity: string
  cost: string
}

/**
 * Форма движения товара (приёмка/списание/перемещение) по образцу экрана продажи:
 * плитки с фото/поиском/сканером штрихкода вместо голого <Select> с товарами
 * «по памяти», несколько позиций за один документ — как реальная накладная.
 */
export function MovementForm({
  mode,
  products,
  warehouses,
  units,
  categories,
  stock,
  fixedWarehouseId,
  onLineRemoved,
  onDone,
  lines: controlledLines,
  onLinesChange,
}: {
  mode: MovementMode
  products: Product[]
  warehouses: Warehouse[]
  units: Unit[]
  categories: Category[]
  stock: StockItem[]
  fixedWarehouseId?: number
  onLineRemoved?: (productId: number) => void
  onDone: () => void
  lines?: MovementLine[]
  onLinesChange?: (lines: MovementLine[]) => void
}) {
  const otherWarehouses = fixedWarehouseId
    ? warehouses.filter((w) => w.id !== fixedWarehouseId)
    : warehouses

  const [warehouseId, setWarehouseId] = useState<number | null>(
    fixedWarehouseId ?? warehouses[0]?.id ?? null,
  )
  const [toWarehouseId, setToWarehouseId] = useState<number | null>(otherWarehouses[0]?.id ?? null)
  const [uncontrolledLines, setUncontrolledLines] = useState<MovementLine[]>(controlledLines ?? [])
  const lines = controlledLines ?? uncontrolledLines
  const setLines = (updater: (prev: MovementLine[]) => MovementLine[]) => {
    const next = updater(lines)
    if (onLinesChange) onLinesChange(next)
    else setUncontrolledLines(next)
  }
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [categoryId, setCategoryId] = useState<number | 'all'>('all')
  const [showScanner, setShowScanner] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const { suppliers, ensureSuppliers } = useCatalog()
  const [withDebt, setWithDebt] = useState(false)
  const [supplierId, setSupplierId] = useState<number | null>(null)
  const [debtDueDate, setDebtDueDate] = useState('')

  useEffect(() => {
    if (mode === 'receive') ensureSuppliers().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode])

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(timer)
  }, [query])

  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code
  const isFractional = (code: string) => units.find((u) => u.code === code)?.fractional ?? false

  // Для списания/перемещения нельзя увести больше, чем реально есть на складе-источнике;
  // приёмка ничем не ограничена — товар только поступает.
  const stockLimited = mode !== 'receive'
  const movementColumns = mode === 'receive' ? '45% 30% 17% 8%' : '70% 22% 8%'
  const stockFor = (productId: number) =>
    warehouseId == null
      ? null
      : Number(stock.find((s) => s.product_id === productId && s.warehouse_id === warehouseId)?.available ?? '0')
  const reservedFor = (productId: number) =>
    warehouseId == null
      ? 0
      : Number(stock.find((s) => s.product_id === productId && s.warehouse_id === warehouseId)?.reserved ?? '0')

  const filtered = useMemo(() => {
    let list = products
    if (categoryId !== 'all') list = list.filter((p) => p.category_id === categoryId)
    if (debouncedQuery.trim()) {
      const q = debouncedQuery.trim().toLowerCase()
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.sku.toLowerCase().includes(q) ||
          (p.barcode ?? '').toLowerCase().includes(q),
      )
    }
    if (stockLimited) {
      list = list.filter((p) => (stockFor(p.id) ?? 0) > 0)
    }
    return list
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [products, categoryId, debouncedQuery, stockLimited, warehouseId, stock])

  function addLine(product: Product) {
    const max = stockLimited ? stockFor(product.id) : null
    const fractional = isFractional(product.unit_code)
    const clamp = (value: number) => (fractional ? value : Math.floor(value))
    setLines((prev) => {
      const existing = prev.find((l) => l.product.id === product.id)
      if (existing) {
        const current = Number(existing.quantity)
        if (max !== null && current >= max) return prev
        const next = clamp(max !== null ? Math.min(current + 1, max) : current + 1)
        return prev.map((l) => (l.product.id === product.id ? { ...l, quantity: String(next) } : l))
      }
      if (max !== null && max <= 0) return prev
      const initial = clamp(max !== null ? Math.min(1, max) : 1)
      if (initial <= 0) return prev
      return [...prev, { product, quantity: String(initial), cost: product.purchase_price ?? '' }]
    })
  }

  function updateLine(productId: number, field: 'quantity' | 'cost', rawValue: string) {
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

  function removeLine(productId: number) {
    // Уводим фокус с кнопки удаления заранее — иначе после удаления строки
    // браузер прокручивает модалку, чтобы вернуть фокус в зону видимости.
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
    setLines((prev) => prev.filter((l) => l.product.id !== productId))
    onLineRemoved?.(productId)
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

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!warehouseId || lines.length === 0) return
    if (mode === 'receive' && withDebt && (!supplierId || !debtDueDate)) {
      setError('Укажите поставщика и срок «Долг до»')
      return
    }
    setError(null)
    setSaving(true)
    try {
      const payloadLines = lines.map((l) => ({
        product_id: l.product.id,
        quantity: l.quantity,
        cost: mode === 'receive' ? l.cost || undefined : undefined,
      }))
      if (mode === 'receive') {
        await receiveGoods({
          warehouse_id: warehouseId,
          lines: payloadLines,
          supplier_id: withDebt ? supplierId : undefined,
          debt_due_date: withDebt ? debtDueDate : undefined,
        })
      } else if (mode === 'write_off') {
        await writeOff({ warehouse_id: warehouseId, lines: payloadLines })
      } else {
        if (!toWarehouseId) return
        await transferStock({ warehouse_id: warehouseId, to_warehouse_id: toWarehouseId, lines: payloadLines })
      }
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось выполнить операцию')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={layoutStyles.form} onSubmit={handleSubmit}>
      <div className={layoutStyles.row}>
        {!fixedWarehouseId && (
          <label className={layoutStyles.field} style={{ flex: 1 }}>
            {mode === 'transfer' ? 'Склад-отправитель' : 'Склад'}
            <Select
              value={warehouseId != null ? String(warehouseId) : ''}
              onChange={(v) => setWarehouseId(Number(v))}
              options={warehouses.map((w) => ({ value: String(w.id), label: w.name }))}
            />
          </label>
        )}
        {mode === 'transfer' && (
          <label className={layoutStyles.field} style={{ flex: 1 }}>
            Склад-получатель
            <Select
              value={toWarehouseId != null ? String(toWarehouseId) : ''}
              onChange={(v) => setToWarehouseId(Number(v))}
              options={otherWarehouses.map((w) => ({ value: String(w.id), label: w.name }))}
            />
          </label>
        )}
      </div>

      <div className="sale-search-panel">
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
        {categories.length > 0 && (
          <div className="sale-filters-row">
            <label className="filter-field">
              <Select
                value={categoryId === 'all' ? 'all' : String(categoryId)}
                onChange={(v) => setCategoryId(v === 'all' ? 'all' : Number(v))}
                options={[
                  { value: 'all', label: 'Все категории' },
                  ...categories.map((c) => ({ value: String(c.id), label: c.name })),
                ]}
              />
            </label>
          </div>
        )}
        {scanError && <p className={layoutStyles.error}>{scanError}</p>}
      </div>

      <div className="sale-results-panel">
        <div className="sale-results-header">
          <span>Товары</span>
          <span className={layoutStyles.textMuted}>{filtered.length} найдено</span>
        </div>
        {filtered.length === 0 ? (
          <p className={layoutStyles.textMuted}>
            {stockLimited ? 'На складе нет товаров, доступных для этой операции' : 'Ничего не найдено'}
          </p>
        ) : (
          <div className="product-grid" style={{ maxHeight: 480, minHeight: 220, overflowY: 'auto' }}>
            {filtered.map((p) => {
              const inLineQty = lines.find((l) => l.product.id === p.id)?.quantity
              const available = stockFor(p.id)
              const reserved = reservedFor(p.id)
              return (
                <div
                  key={p.id}
                  role="button"
                  tabIndex={0}
                  className={`product-tile${inLineQty ? ' product-tile-in-cart' : ''}`}
                  onClick={() => addLine(p)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      addLine(p)
                    }
                  }}
                >
                  <ProductPhoto src={p.photo} />
                  <div className="product-tile-body">
                    <span className="product-tile-name">{p.name}</span>
                    {available !== null && (
                      <span className="product-tile-stock">
                        <span className="product-tile-stock-label">
                          Остаток:
                          {reserved > 0 && (
                            <InfoHint
                              text={`${formatQuantity(String(reserved))} ${unitName(p.unit_code)} зарезервировано на заказы клиентов и недоступно для этой операции — освободится, когда заказ выдадут или отменят.`}
                            />
                          )}
                        </span>
                        <span className="product-tile-stock-value">
                          {formatQuantity(available)} {unitName(p.unit_code)}
                        </span>
                      </span>
                    )}
                  </div>
                  <span
                    className={`product-tile-cart-badge${inLineQty ? '' : ' product-tile-cart-badge-hidden'}`}
                  >
                    {inLineQty ? (
                      <>
                        {formatQuantity(inLineQty)}
                        <IconButton
                          variant="neutral"
                          className="product-tile-remove"
                          onClick={(e) => {
                            e.stopPropagation()
                            removeLine(p.id)
                          }}
                          aria-label="Убрать из списка"
                        >
                          <IconTrash size={10} stroke={2} />
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
            <h3>{MODE_LABELS[mode]}</h3>
            <span className={layoutStyles.textMuted}>{lines.length} поз.</span>
          </div>
          <div className="table-wrap cart-table-wrap">
            <div className="cart-table-head" style={{ gridTemplateColumns: movementColumns }}>
              <span>Товар</span>
              <span>Кол-во</span>
              {mode === 'receive' && <span>Закуп. цена</span>}
              <span />
            </div>
            <div>
              {lines.map((line) => {
                const available = stockFor(line.product.id)
                const overStock = stockLimited && available !== null && Number(line.quantity || 0) > available
                return (
                  <div
                    key={line.product.id}
                    className="cart-table-row"
                    style={{ gridTemplateColumns: movementColumns }}
                  >
                    <div className="cart-table-name">
                      <div>{line.product.name}</div>
                      {available !== null && (
                        <div className="cart-table-stock">
                          Остаток: {formatQuantity(available)} {unitName(line.product.unit_code)}
                        </div>
                      )}
                    </div>
                    <div className="cart-table-qty-cell">
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
                            onClick={() => addLine(line.product)}
                            aria-label="Увеличить количество"
                          >
                            <IconChevronRight size={10} stroke={1.8} className="cart-qty-step-icon-up" />
                          </IconButton>
                          <IconButton
                            variant="muted"
                            className="cart-qty-step"
                            onClick={() =>
                              updateLine(line.product.id, 'quantity', String(Math.max(0, Number(line.quantity) - 1)))
                            }
                            aria-label="Уменьшить количество"
                          >
                            <IconChevronRight size={10} stroke={1.8} className="cart-qty-step-icon-down" />
                          </IconButton>
                        </div>
                      </div>
                      {overStock && available !== null && (
                        <div className="cart-table-warning">больше остатка ({formatQuantity(available)})</div>
                      )}
                    </div>
                    {mode === 'receive' && (
                      <div className="cart-table-price-cell">
                        <input
                          type="text"
                          inputMode="decimal"
                          value={line.cost}
                          onChange={(e) => updateLine(line.product.id, 'cost', e.target.value)}
                        />
                        <span className="cart-table-price-suffix">₽</span>
                      </div>
                    )}
                    <div>
                      <IconButton
                        variant="danger"
                        onClick={() => removeLine(line.product.id)}
                        aria-label="Убрать позицию"
                      >
                        <IconTrash size={16} stroke={1.8} />
                      </IconButton>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {mode === 'receive' && lines.length > 0 && (
        <div className={layoutStyles.stack} style={{ gap: 10 }}>
          <label className="sale-checkbox">
            <input type="checkbox" checked={withDebt} onChange={(e) => setWithDebt(e.target.checked)} />
            Принять в долг поставщику
          </label>
          {withDebt && (
            <div className={layoutStyles.row}>
              <label className={layoutStyles.field} style={{ flex: 1 }}>
                Поставщик
                <Select
                  value={supplierId != null ? String(supplierId) : ''}
                  onChange={(v) => setSupplierId(v ? Number(v) : null)}
                  options={suppliers.map((s) => ({ value: String(s.id), label: s.name }))}
                />
              </label>
              <label className={layoutStyles.field} style={{ flex: 1 }}>
                Долг до
                <DateInput
                  value={debtDueDate}
                  min={new Date().toISOString().slice(0, 10)}
                  onChange={setDebtDueDate}
                />
              </label>
            </div>
          )}
        </div>
      )}

      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button
        type="submit"
        disabled={
          saving ||
          !warehouseId ||
          lines.length === 0 ||
          (mode === 'transfer' && !toWarehouseId) ||
          (mode === 'receive' && withDebt && (!supplierId || !debtDueDate)) ||
          lines.some((l) => Number(l.quantity) <= 0)
        }
      >
        {saving ? 'Проведение…' : `Провести: ${MODE_LABELS[mode]}`}
      </Button>
    </form>
  )
}
