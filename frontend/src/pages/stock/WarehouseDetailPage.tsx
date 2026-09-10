import { useEffect, useRef, useState, type CSSProperties, type FormEvent } from 'react'
import { createPortal } from 'react-dom'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  setWarehouseAssignments,
  updateWarehouseDetails,
  getRestockRecommendations,
  type StockItem,
  type Warehouse,
  type RestockRecommendation,
} from '../../entities/inventory/api'
import type { Product } from '../../entities/product/api'
import { createTask, listActiveTasks } from '../../entities/task/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { useCatalog } from '../../app/CatalogContext'
import { useShop } from '../../app/ShopContext'
import { Modal } from '../../shared/ui/Modal'
import {
  IconChevronLeft,
  IconPencil,
  IconTrendingUp,
  IconShoppingCart,
  IconPlus,
  IconCheck,
  IconX,
  IconClipboardCheck,
  IconTruck,
  IconSearch,
  IconShare,
  IconPackage,
  IconAlertTriangle,
  IconMapPin,
  IconUsers,
  IconArrowBarToDown,
} from '@tabler/icons-react'
import { IconButton } from '../../shared/ui/IconButton'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { ResetFiltersButton } from '../../shared/ui/ResetFiltersButton'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { StockWarningIcon } from '../../shared/ui/StockWarningIcon'
import { formatQuantity, isLowStock, isOutOfStock, normalizeDecimalInput } from '../../shared/lib/format'
import { loadRestockCart, saveRestockCart } from './restockCart'
import {
  AssignedUsersField,
  MODE_LABELS,
  MODE_ICONS,
  useWarehouseManagerCandidates,
  type MovementMode,
} from './shared'
import layoutStyles from '../../shared/ui/Layout.module.css'
import detail from '../products/ProductDetailPage.module.css'
import styles from './WarehouseDetailPage.module.css'

const STOCK_COLUMNS = '2fr 1fr 1fr 1fr'

function pulseTasksNav() {
  document.querySelectorAll('[data-nav="tasks"]').forEach((el) => {
    el.classList.remove('nav-pulse')
    // reflow, чтобы анимация перезапустилась при повторных кликах подряд
    void (el as HTMLElement).offsetWidth
    el.classList.add('nav-pulse')
    el.addEventListener('animationend', () => el.classList.remove('nav-pulse'), { once: true })
  })
}

export function WarehouseDetailPage() {
  const { id } = useParams<{ id: string }>()
  const warehouseId = Number(id)
  const navigate = useNavigate()
  const { user } = useAuth()
  const { shop } = useShop()
  const canManageWarehouses = user?.role === 'owner' || user?.role === 'manager'

  const {
    products,
    units,
    categories,
    employees,
    warehouses,
    stock: allStock,
    ensureProducts,
    ensureUnits,
    ensureCategories,
    ensureEmployees,
    ensureWarehouses,
    ensureStock,
    refresh: refreshCatalog,
  } = useCatalog()
  const warehouse = warehouses.find((w) => w.id === warehouseId) ?? null
  const [recommendations, setRecommendations] = useState<RestockRecommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [restockCartIds, setRestockCartIds] = useState<number[]>(() => loadRestockCart(warehouseId).ids)
  const [restockCartQuantities, setRestockCartQuantities] = useState<Record<number, string>>(
    () => loadRestockCart(warehouseId).quantities,
  )
  const [restockNotice, setRestockNotice] = useState<string | null>(null)
  const [restockedProductIds, setRestockedProductIds] = useState<Set<number>>(new Set())
  const [showEdit, setShowEdit] = useState(false)
  const [stockQuery, setStockQuery] = useState('')
  const [stockCategoryId, setStockCategoryId] = useState<number | 'all'>('all')
  const [showAllProducts, setShowAllProducts] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()

  // При быстром переключении между складами более старый ответ
  // getRestockRecommendations(prevId) может прийти позже нового —
  // currentIdRef защищает от перезаписи состояния данными чужого склада.
  const currentIdRef = useRef(warehouseId)

  async function load(silent = false) {
    const requestedId = warehouseId
    currentIdRef.current = requestedId
    if (!silent) setLoading(true)
    try {
      const [, , , , , , rec, activeTasks] = await Promise.all([
        ensureStock(),
        ensureWarehouses(),
        ensureProducts(),
        ensureUnits(),
        ensureCategories(),
        canManageWarehouses ? ensureEmployees() : Promise.resolve(),
        getRestockRecommendations(warehouseId),
        listActiveTasks(),
      ])
      if (currentIdRef.current !== requestedId) return
      setRecommendations(rec)
      setRestockedProductIds(
        new Set(
          activeTasks
            .filter((t) => t.type === 'restock' && t.warehouse_id === warehouseId && t.product_id != null)
            .map((t) => t.product_id!),
        ),
      )

      if (searchParams.get('open') === 'receive') {
        setSearchParams(
          (prev) => {
            const next = new URLSearchParams(prev)
            next.delete('open')
            return next
          },
          { replace: true },
        )
        navigate(`/stock/${warehouseId}/movement/receive`, { replace: true })
        return
      }
    } catch (err) {
      if (currentIdRef.current === requestedId) {
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить остатки')
      }
    } finally {
      if (!silent && currentIdRef.current === requestedId) setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [warehouseId])

  // Список дозаказа — свой на каждый склад, переживает перезагрузку/переход между страницами
  useEffect(() => {
    const cart = loadRestockCart(warehouseId)
    setRestockCartIds(cart.ids)
    setRestockCartQuantities(cart.quantities)
  }, [warehouseId])

  useEffect(() => {
    saveRestockCart(warehouseId, { ids: restockCartIds, quantities: restockCartQuantities })
  }, [warehouseId, restockCartIds, restockCartQuantities])

  const productById = (pid: number) => products.find((p) => p.id === pid)
  const productName = (pid: number) => productById(pid)?.name ?? `#${pid}`
  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code
  const employeeName = (uid: number) =>
    uid === user?.id ? `${user.name} (вы)` : employees.find((e) => e.id === uid)?.name ?? `#${uid}`

  const warehouseStock = allStock.filter((item) => item.warehouse_id === warehouseId)

  // "Показать все товары" дополняет список нулевыми позициями для товаров, которые
  // никогда не поступали на этот склад — иначе не видно, что товар вообще можно
  // принять именно сюда (в списке его просто не было)
  const stockWithZeros = showAllProducts
    ? [
        ...warehouseStock,
        ...products
          .filter((p) => !warehouseStock.some((item) => item.product_id === p.id))
          .map(
            (p): StockItem => ({
              product_id: p.id,
              variant_id: null,
              warehouse_id: warehouseId,
              quantity: '0',
              reserved: '0',
              available: '0',
            }),
          ),
      ]
    : warehouseStock

  const stock = stockWithZeros
    .filter((item) => {
      if (stockCategoryId === 'all') return true
      return productById(item.product_id)?.category_id === stockCategoryId
    })
    .filter((item) => {
      if (!stockQuery.trim()) return true
      const q = stockQuery.trim().toLowerCase()
      const product = productById(item.product_id)
      return (
        product?.name.toLowerCase().includes(q) ||
        product?.sku.toLowerCase().includes(q) ||
        (product?.barcode ?? '').toLowerCase().includes(q)
      )
    })
    .sort((a, b) => Number(b.quantity) - Number(a.quantity) || productName(a.product_id).localeCompare(productName(b.product_id)))

  const stockPositionsCount = warehouseStock.length
  const lowStockCount = warehouseStock.filter((item) => {
    const product = productById(item.product_id)
    return product != null && isLowStock(item.quantity, product.min_stock)
  }).length
  const assigneesSummary =
    warehouse == null || warehouse.assigned_user_ids.length === 0
      ? 'Только владелец/управляющий'
      : warehouse.assigned_user_ids.map(employeeName).join(', ')

  async function createRestockTasks() {
    const items = restockCartIds
      .map((id) => recommendations.find((r) => r.product_id === id))
      .filter((r): r is RestockRecommendation => r != null)
    if (items.length === 0) return
    try {
      // последовательно — сквозной номер задачи выдаётся по max()+1, параллельные
      // запросы могут получить одно и то же число и столкнуться на уникальности
      for (const rec of items) {
        await createTask({
          title: `Дозаказать: ${rec.product_name}`,
          type: 'restock',
          product_id: rec.product_id,
          warehouse_id: warehouseId,
          quantity: restockCartQuantities[rec.product_id] || '1',
        })
      }
      setRestockCartIds([])
      setRestockCartQuantities({})
      setRestockedProductIds((prev) => new Set([...prev, ...items.map((i) => i.product_id)]))
      setRestockNotice(
        items.length === 1
          ? `Задача «Дозаказать: ${items[0].product_name}» поставлена`
          : `Поставлено задач на дозаказ: ${items.length}`,
      )
      pulseTasksNav()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать задачи на дозаказ')
    }
  }

  useEffect(() => {
    if (!restockNotice) return
    const timer = setTimeout(() => setRestockNotice(null), 5000)
    return () => clearTimeout(timer)
  }, [restockNotice])

  if (!loading && !warehouse) {
    return (
      <div className={layoutStyles.stack}>
        <Link to="/stock" className={layoutStyles.backLink}>
          <IconChevronLeft size={16} stroke={1.8} /> Все склады
        </Link>
        <p className={layoutStyles.error}>Склад не найден</p>
      </div>
    )
  }

  return (
    <div className={layoutStyles.stack}>
      <Link to="/stock" className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> Все склады
      </Link>

      {warehouse && (
        <>
          <section
            className={`${styles.hero} ${detail.reveal}`}
            style={{ '--reveal-delay': '0ms' } as CSSProperties}
          >
            <div className={styles.heroIcon}>
              <IconPackage size={28} stroke={1.6} />
            </div>
            <div className={detail.heroBody}>
              <div className={detail.heroTop}>
                <div className={detail.heroHeading}>
                  <h2 className={detail.heroTitle}>{warehouse.name}</h2>
                  <div className={detail.heroTags}>
                    {warehouse.show_on_storefront && (
                      <span className={detail.storefrontChip}>На витрине</span>
                    )}
                  </div>
                </div>
                <div className={styles.heroActions}>
                  {shop?.storefront_enabled && shop.slug && (
                    <IconButton
                      variant="muted"
                      size="lg"
                      tooltip="Поделиться витриной склада"
                      aria-label="Поделиться витриной склада"
                      onClick={() => {
                        const url = `${window.location.origin}/store/${shop.slug}?warehouse_id=${warehouseId}`
                        navigator.clipboard?.writeText(url).catch(() => {})
                        window.open(url, '_blank', 'noopener,noreferrer')
                      }}
                    >
                      <IconShare size={20} stroke={1.8} />
                    </IconButton>
                  )}
                  {canManageWarehouses && (
                    <IconButton
                      variant="muted"
                      size="lg"
                      tooltip="Изменить склад"
                      aria-label="Изменить склад"
                      onClick={() => setShowEdit(true)}
                    >
                      <IconPencil size={20} stroke={1.8} />
                    </IconButton>
                  )}
                  {(Object.keys(MODE_LABELS) as MovementMode[]).map((m) => {
                    const Icon = MODE_ICONS[m]
                    return (
                      <IconButton
                        key={m}
                        variant="accent"
                        size="lg"
                        tooltip={MODE_LABELS[m]}
                        onClick={() => navigate(`/stock/${warehouseId}/movement/${m}`)}
                      >
                        <Icon size={22} stroke={1.8} />
                      </IconButton>
                    )
                  })}
                </div>
              </div>
              <div className={detail.heroMeta}>
                {warehouse.address && (
                  <span>
                    <IconMapPin size={15} stroke={1.8} />
                    {warehouse.address}
                  </span>
                )}
                <span>
                  <IconUsers size={15} stroke={1.8} />
                  {assigneesSummary}
                </span>
              </div>
            </div>
          </section>

          <section
            className={`${detail.metrics} ${detail.reveal}`}
            style={{ '--reveal-delay': '60ms' } as CSSProperties}
          >
            <div className={detail.metric}>
              <span className={detail.metricIcon}>
                <IconPackage size={18} stroke={1.8} />
              </span>
              <div className={detail.metricBody}>
                <strong>{stockPositionsCount}</strong>
                <span>Позиций на складе</span>
              </div>
            </div>
            <div className={detail.metric}>
              <span className={`${detail.metricIcon} ${lowStockCount > 0 ? detail.metricIconWarn : ''}`}>
                <IconAlertTriangle size={18} stroke={1.8} />
              </span>
              <div className={detail.metricBody}>
                <strong>{lowStockCount}</strong>
                <span>Мало на складе</span>
              </div>
            </div>
            <div className={detail.metric}>
              <span className={`${detail.metricIcon} ${recommendations.length > 0 ? detail.metricIconWarn : ''}`}>
                <IconTrendingUp size={18} stroke={1.8} />
              </span>
              <div className={detail.metricBody}>
                <strong>{recommendations.length}</strong>
                <span>К дозаказу</span>
              </div>
            </div>
            <div className={detail.metric}>
              <span className={detail.metricIcon}>
                <IconUsers size={18} stroke={1.8} />
              </span>
              <div className={detail.metricBody}>
                <strong>{warehouse.assigned_user_ids.length || '—'}</strong>
                <span>Ответственных</span>
              </div>
            </div>
          </section>
        </>
      )}

      {showEdit && warehouse && (
        <Modal title={`Изменить склад · ${warehouse.name}`} onClose={() => setShowEdit(false)}>
          <WarehouseEditForm
            warehouse={warehouse}
            onDone={() => {
              setShowEdit(false)
              refreshCatalog(['warehouses']).catch(() => {})
            }}
          />
        </Modal>
      )}

      {error && <p className={layoutStyles.error}>{error}</p>}

      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : !allStock.some((item) => item.warehouse_id === warehouseId) && !showAllProducts ? (
        <div className={`${layoutStyles.stack} ${detail.reveal}`} style={{ gap: 8, '--reveal-delay': '110ms' } as CSSProperties}>
          <p className={layoutStyles.textMuted}>На этом складе остатков пока нет</p>
          {products.length > 0 && (
            <button type="button" className="disclosure-link" onClick={() => setShowAllProducts(true)}>
              Показать все товары компании, чтобы принять сюда
            </button>
          )}
        </div>
      ) : (
        <div className={`${layoutStyles.stack} ${detail.reveal}`} style={{ '--reveal-delay': '110ms' } as CSSProperties}>
          <h3 className={detail.sectionTitle}>Товары на складе</h3>
          <div className="sale-search-panel">
            <div className="sale-search-row">
              <IconSearch size={16} stroke={1.8} className="sale-search-icon" />
              <input
                className="sale-search-input"
                placeholder="Поиск по названию, артикулу, штрихкоду…"
                value={stockQuery}
                onChange={(e) => setStockQuery(e.target.value)}
              />
            </div>
            <div className="sale-filters-row">
              {categories.length > 0 && (
                <label className="filter-field">
                  <Select
                    value={stockCategoryId === 'all' ? 'all' : String(stockCategoryId)}
                    onChange={(v) => setStockCategoryId(v === 'all' ? 'all' : Number(v))}
                    options={[
                      { value: 'all', label: 'Все категории' },
                      ...categories.map((c) => ({ value: String(c.id), label: c.name })),
                    ]}
                  />
                </label>
              )}
              <label className="sale-checkbox">
                <input
                  type="checkbox"
                  checked={showAllProducts}
                  onChange={(e) => setShowAllProducts(e.target.checked)}
                />
                Все товары компании
              </label>
              {(stockQuery.trim() || stockCategoryId !== 'all') && (
                <ResetFiltersButton
                  onClick={() => {
                    setStockQuery('')
                    setStockCategoryId('all')
                  }}
                />
              )}
            </div>
          </div>

          {stock.length === 0 ? (
            <p className="text-muted">Ничего не найдено</p>
          ) : (
            <div className="data-table">
              <div className="data-table-head" style={{ gridTemplateColumns: STOCK_COLUMNS }}>
                <span>Товар</span>
                <span>Артикул</span>
                <span>Остаток</span>
                <span>Мин. остаток</span>
              </div>
              <div className="data-table-body">
                {stock.map((item, i) => {
                  const product = productById(item.product_id)
                  const out = isOutOfStock(item.quantity)
                  const low = product != null && isLowStock(item.quantity, product.min_stock)
                  return (
                    <button
                      key={i}
                      type="button"
                      className="data-row data-row-link sale-history-row-in"
                      style={
                        {
                          gridTemplateColumns: STOCK_COLUMNS,
                          '--row-delay': `${Math.min(i, 12) * 25}ms`,
                        } as CSSProperties
                      }
                      onClick={() => product && navigate(`/products/${product.id}`)}
                    >
                      <span className="data-row-name">{productName(item.product_id)}</span>
                      <span className="text-muted">{product?.sku || '—'}</span>
                      <span
                        className={`data-row-qty${out ? ' data-row-qty-out' : low ? ' data-row-qty-low' : ''}`}
                      >
                        {formatQuantity(item.quantity)} {unitName(product?.unit_code ?? 'pcs')}
                        {low && <StockWarningIcon />}
                      </span>
                      <span className="text-muted">
                        {product ? `${formatQuantity(product.min_stock)} ${unitName(product.unit_code)}` : '—'}
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {!loading && recommendations.length > 0 && (
        <div className="stack">
          <div className="row" style={{ gap: 6 }}>
            <IconTrendingUp size={18} stroke={1.8} className={styles['restock-title-icon']} />
            <h3>Стоит дозаказать</h3>
          </div>
          <p className="text-muted">
            Заканчивается, но хорошо продаётся — раскупили за последний месяц, есть смысл пополнить.
          </p>
          <div className="product-grid">
            {recommendations.map((rec) => {
              const product = productById(rec.product_id)
              const inCart = restockCartIds.includes(rec.product_id)
              const alreadyRestocked = restockedProductIds.has(rec.product_id)
              function toggleCart() {
                setRestockCartIds((prev) =>
                  inCart ? prev.filter((id) => id !== rec.product_id) : [...prev, rec.product_id],
                )
                setRestockCartQuantities((prev) => {
                  if (inCart) {
                    const { [rec.product_id]: _removed, ...rest } = prev
                    return rest
                  }
                  return { ...prev, [rec.product_id]: '1' }
                })
              }
              return (
                <div
                  key={rec.product_id}
                  role="button"
                  tabIndex={0}
                  aria-pressed={inCart}
                  aria-label={`${rec.product_name} — ${inCart ? 'убрать из списка дозаказа' : 'добавить в список дозаказа'}`}
                  className={`product-tile ${styles['restock-tile']}`}
                  onClick={toggleCart}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      toggleCart()
                    }
                  }}
                >
                  {alreadyRestocked && (
                    <span className={styles['restock-tile-badge']} title="Уже есть активная задача на дозаказ">
                      <IconTruck size={11} stroke={2} /> В задаче
                    </span>
                  )}
                  <span
                    aria-hidden="true"
                    className={[styles['restock-tile-add'], inCart && styles['restock-tile-add-checked']].filter(Boolean).join(' ')}
                  >
                    {inCart ? <IconCheck size={16} stroke={1.8} /> : <IconPlus size={16} stroke={1.8} />}
                  </span>
                  <div className={styles['restock-tile-photo-link']}>
                    <ProductPhoto src={product?.photo ?? ''} />
                  </div>
                  <div className="product-tile-body">
                    <span className={`product-tile-name ${styles['restock-tile-name-btn']}`}>
                      {rec.product_name}
                    </span>
                    <span className="product-tile-stock product-tile-stock-out">
                      <span className="product-tile-stock-label">Остаток:</span>
                      <span className="product-tile-stock-value-wrap">
                        <span className="product-tile-stock-value">
                          {formatQuantity(rec.quantity)} {unitName(product?.unit_code ?? 'pcs')}
                        </span>
                      </span>
                    </span>
                    <span className="product-tile-stock">
                      <span className="product-tile-stock-label">Продано:</span>
                      <span className="product-tile-stock-value-wrap">
                        <span className="product-tile-stock-value">{formatQuantity(rec.quantity_sold)}</span>
                      </span>
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {restockNotice && (
        <RestockTaskToast message={restockNotice} onClose={() => setRestockNotice(null)} />
      )}

      <RestockCartMenu
        recommendations={recommendations}
        productById={productById}
        unitName={unitName}
        isFractional={(code) => units.find((u) => u.code === code)?.fractional ?? false}
        cartIds={restockCartIds}
        quantities={restockCartQuantities}
        onQuantityChange={(id, value) => setRestockCartQuantities((prev) => ({ ...prev, [id]: value }))}
        onRemove={(id) => {
          setRestockCartIds((prev) => prev.filter((x) => x !== id))
          setRestockCartQuantities((prev) => {
            const { [id]: _removed, ...rest } = prev
            return rest
          })
        }}
        onClear={() => {
          setRestockCartIds([])
          setRestockCartQuantities({})
        }}
        onSubmit={createRestockTasks}
      />
    </div>
  )
}

function RestockTaskToast({ message, onClose }: { message: string; onClose: () => void }) {
  return createPortal(
    <div className="restock-toast" role="status">
      <span className="restock-toast-icon">
        <IconClipboardCheck size={20} stroke={1.8} />
      </span>
      <div className="restock-toast-body">
        <span className="restock-toast-title">{message}</span>
        <span className="restock-toast-hint">
          Это задача для склада, а не приёмка товара — выполнит тот, кто привезёт заказ.{' '}
          <Link to="/tasks" onClick={onClose}>
            Открыть задачи
          </Link>
        </span>
      </div>
      <button type="button" className="restock-toast-close" onClick={onClose} aria-label="Закрыть">
        <IconX size={14} stroke={1.8} />
      </button>
    </div>,
    document.body,
  )
}

function RestockCartMenu({
  recommendations,
  productById,
  unitName,
  isFractional,
  cartIds,
  quantities,
  onQuantityChange,
  onRemove,
  onClear,
  onSubmit,
}: {
  recommendations: RestockRecommendation[]
  productById: (id: number) => Product | undefined
  unitName: (code: string) => string
  isFractional: (code: string) => boolean
  cartIds: number[]
  quantities: Record<number, string>
  onQuantityChange: (id: number, value: string) => void
  onRemove: (id: number) => void
  onClear: () => void
  onSubmit: () => void
}) {
  const [open, setOpen] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const triggerRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  const items = cartIds
    .map((id) => recommendations.find((r) => r.product_id === id))
    .filter((r): r is RestockRecommendation => r != null)

  const hadItemsRef = useRef(items.length > 0)
  useEffect(() => {
    if (items.length > 0) {
      hadItemsRef.current = true
      setLeaving(false)
      return
    }
    if (!hadItemsRef.current) return
    hadItemsRef.current = false
    setOpen(false)
    setLeaving(true)
    const timer = setTimeout(() => setLeaving(false), 220)
    return () => clearTimeout(timer)
  }, [items.length])

  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node
      if (triggerRef.current?.contains(target) || panelRef.current?.contains(target)) return
      setOpen(false)
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open])

  function removeItem(id: number) {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
    onRemove(id)
  }

  if (items.length === 0 && !leaving) return null

  return createPortal(
    <>
      {!open && (
        <div
          ref={triggerRef}
          className={[styles['restock-cart-trigger'], leaving && styles['restock-cart-trigger-out']].filter(Boolean).join(' ')}
        >
          <button
            type="button"
            className={styles['restock-cart-fab']}
            aria-label="Список дозаказа"
            onClick={() => setOpen(true)}
          >
            <IconShoppingCart size={24} stroke={1.8} />
          </button>
          <span key={items.length} className={styles['restock-cart-badge']}>
            {items.length}
          </span>
        </div>
      )}

      {open && (
        <div ref={panelRef} className={styles['restock-cart-panel']}>
          <div className={styles['restock-cart-panel-header']}>
            <span className={styles['restock-cart-panel-title']}>Список дозаказа</span>
            <div className="row" style={{ gap: 4 }}>
              <button
                type="button"
                className={styles['restock-cart-clear']}
                onClick={() => {
                  setOpen(false)
                  onClear()
                }}
              >
                Очистить
              </button>
              <IconButton
                variant="neutral"
                aria-label="Закрыть"
                onClick={() => setOpen(false)}
              >
                <IconX size={16} stroke={1.8} />
              </IconButton>
            </div>
          </div>
          <div className={styles['restock-cart-list']}>
            {items.map((rec) => {
              const product = productById(rec.product_id)
              const unit = unitName(product?.unit_code ?? 'pcs')
              return (
                <div key={rec.product_id} className={styles['restock-cart-row']}>
                  <div className={styles['restock-cart-row-name']}>
                    <div>{rec.product_name}</div>
                    <div className="cart-table-stock">
                      Остаток: {formatQuantity(rec.quantity)} {unit}
                    </div>
                  </div>
                  <label className={styles['restock-cart-row-qty']}>
                    <input
                      type="text"
                      inputMode="decimal"
                      value={quantities[rec.product_id] ?? '1'}
                      onChange={(e) => {
                        const normalized = normalizeDecimalInput(e.target.value)
                        if (normalized === null) return
                        const value =
                          !isFractional(product?.unit_code ?? 'pcs') && normalized.includes('.')
                            ? normalized.split('.')[0] || '0'
                            : normalized
                        onQuantityChange(rec.product_id, value)
                      }}
                      onClick={(e) => e.stopPropagation()}
                    />
                    <span className={`text-muted ${styles['restock-cart-row-unit']}`}>{unit}</span>
                  </label>
                  <IconButton
                    className={styles['restock-cart-row-remove']}
                    aria-label="Убрать из списка"
                    onClick={() => removeItem(rec.product_id)}
                  >
                    <IconX size={14} stroke={1.8} />
                  </IconButton>
                </div>
              )
            })}
          </div>
          <button
            type="button"
            className={styles['restock-cart-submit']}
            onClick={() => {
              setOpen(false)
              onSubmit()
            }}
          >
            <IconArrowBarToDown size={18} stroke={2} />
            Дозаказать
          </button>
        </div>
      )}
    </>,
    document.body,
  )
}

function WarehouseEditForm({
  warehouse,
  onDone,
}: {
  warehouse: Warehouse
  onDone: () => void
}) {
  const [name, setName] = useState(warehouse.name)
  const [address, setAddress] = useState(warehouse.address)
  const [showOnStorefront, setShowOnStorefront] = useState(warehouse.show_on_storefront ?? false)
  const [selectedIds, setSelectedIds] = useState<number[]>(warehouse.assigned_user_ids)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const candidates = useWarehouseManagerCandidates()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await updateWarehouseDetails(warehouse.id, {
        name,
        address,
        show_on_storefront: showOnStorefront,
      })
      await setWarehouseAssignments(warehouse.id, selectedIds)
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить склад')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="field">
        Название
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className="field">
        Адрес
        <input value={address} onChange={(e) => setAddress(e.target.value)} />
      </label>
      <label className="sale-checkbox">
        <input
          type="checkbox"
          checked={showOnStorefront}
          onChange={(e) => setShowOnStorefront(e.target.checked)}
        />
        Показывать на витрине
      </label>
      <p className="text-muted" style={{ margin: '-6px 0 0', fontSize: 13, lineHeight: 1.4 }}>
        Учитывается в наличии для покупателей. Если ни один склад не отмечен — на витрине везде
        «нет в наличии».
      </p>
      <label className="field">
        Ответственные
        <AssignedUsersField candidates={candidates} selectedIds={selectedIds} onChange={setSelectedIds} />
      </label>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Сохранить'}
      </Button>
    </form>
  )
}
