import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  listProducts,
  exportProducts,
  type Product,
  type ProductKind,
  type ExportFormat,
} from '../../entities/product/api'
import { useCatalog } from '../../app/CatalogContext'
import { ApiError } from '../../shared/api/client'
import { ImportProductsModal } from './ImportProductsModal'
import { categoryOptions } from './ProductForm'
import {
  IconPlus,
  IconUpload,
  IconDownload,
  IconChevronDown,
  IconSearch,
  IconDots,
} from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Select } from '../../shared/ui/Select'
import { DropdownMenu } from '../../shared/ui/DropdownMenu'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { StockWarningIcon } from '../../shared/ui/StockWarningIcon'
import { InfoHint } from '../../shared/ui/InfoHint'
import { ResetFiltersButton } from '../../shared/ui/ResetFiltersButton'
import { EmptyState } from '../../shared/ui/EmptyState'
import {
  formatMoney,
  formatQuantity,
  isLowStock,
  isOutOfStock,
} from '../../shared/lib/format'
import { useAuth } from '../../app/AuthContext'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './ProductsPage.module.css'

const EXPORT_FORMAT_LABELS: Record<ExportFormat, string> = {
  xlsx: 'Excel (.xlsx)',
  csv: 'CSV (.csv)',
  pdf: 'PDF (.pdf)',
}

const IMPORT_FORMAT_LABELS: Record<'xlsx' | 'csv', string> = {
  xlsx: 'Excel (.xlsx)',
  csv: 'CSV (.csv)',
}

async function downloadExport(format: ExportFormat) {
  const blob = await exportProducts(format)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `tovary.${format}`
  link.click()
  URL.revokeObjectURL(url)
}

const PAGE_SIZE = 50

const KIND_TABS: { value: ProductKind; label: string }[] = [
  { value: 'product', label: 'Товары' },
  { value: 'service', label: 'Услуги' },
]

type SortMode =
  | 'name'
  | 'price_asc'
  | 'price_desc'
  | 'margin_desc'
  | 'stock_desc'
  | 'created_desc'
  | 'created_asc'

const SORT_LABELS: Record<SortMode, string> = {
  name: 'По названию',
  price_asc: 'Цена: сначала дешёвые',
  price_desc: 'Цена: сначала дорогие',
  margin_desc: 'По марже',
  stock_desc: 'По остатку',
  created_desc: 'Сначала новые',
  created_asc: 'Сначала старые',
}

export function ProductsPage() {
  const { user } = useAuth()
  const canManage = user?.role === 'owner' || user?.role === 'manager'
  const navigate = useNavigate()

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
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [searchParams, setSearchParams] = useSearchParams()

  // ?query= — переход из поиска в шапке/сайдбаре (GlobalSearch): список сразу
  // открывается отфильтрованным, без второго ввода того же запроса
  // вкладка «Товары» / «Услуги». В адресе, чтобы ссылка на услуги
  // открывалась сразу на нужной вкладке и работала кнопка «назад»
  const kind: ProductKind = searchParams.get('kind') === 'service' ? 'service' : 'product'
  const isServices = kind === 'service'
  const [query, setQuery] = useState(() => searchParams.get('query') ?? '')
  const [debouncedQuery, setDebouncedQuery] = useState(query)
  const [categoryId, setCategoryId] = useState<number | 'all'>('all')
  const [warehouseId, setWarehouseId] = useState<number | 'all'>('all')
  const [sortMode, setSortMode] = useState<SortMode>('name')
  const [inStockOnly, setInStockOnly] = useState(false)

  const [importFormat, setImportFormat] = useState<'xlsx' | 'csv' | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)


  // Старые ссылки /products?open= / ?highlight= → страница товара
  useEffect(() => {
    const openId = searchParams.get('open') ?? searchParams.get('highlight')
    if (!openId) return
    navigate(`/products/${openId}`, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleExport(format: ExportFormat) {
    setExportError(null)
    try {
      await downloadExport(format)
    } catch (err) {
      setExportError(err instanceof ApiError ? err.message : 'Не удалось выгрузить файл')
    }
  }

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(timer)
  }, [query])

  const requestRef = useRef(0)

  async function loadProducts() {
    // ответ на устаревший запрос (поиск печатают быстрее, чем отвечает сервер)
    // не должен затирать свежий список
    const request = ++requestRef.current
    setLoading(true)
    setError(null)
    try {
      const { items, total: t } = await listProducts({
        query: debouncedQuery,
        limit: PAGE_SIZE,
        offset: 0,
        categoryId: categoryId === 'all' ? null : categoryId,
        sort: sortMode,
        inStockOnly,
        warehouseId: warehouseId === 'all' ? null : warehouseId,
        kind,
      })
      if (request !== requestRef.current) return
      setProducts(items)
      setTotal(t)
    } catch (err) {
      if (request !== requestRef.current) return
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить товары')
    } finally {
      if (request === requestRef.current) setLoading(false)
    }
  }

  async function loadMore() {
    const request = requestRef.current
    setLoadingMore(true)
    try {
      const { items, total: t } = await listProducts({
        query: debouncedQuery,
        limit: PAGE_SIZE,
        offset: products.length,
        categoryId: categoryId === 'all' ? null : categoryId,
        sort: sortMode,
        inStockOnly,
        warehouseId: warehouseId === 'all' ? null : warehouseId,
        kind,
      })
      if (request !== requestRef.current) return // фильтры сменились — страница от другого списка
      setProducts((prev) => [...prev, ...items])
      setTotal(t)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить товары')
    } finally {
      setLoadingMore(false)
    }
  }

  useEffect(() => {
    loadProducts()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQuery, categoryId, sortMode, inStockOnly, warehouseId, kind])

  useEffect(() => {
    ensureCategories().catch(() => {})
    ensureUnits().catch(() => {})
    ensureStock().catch(() => {})
    ensureWarehouses().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code
  const stockFor = (productId: number) =>
    stock
      .filter((s) => s.product_id === productId && (warehouseId === 'all' || s.warehouse_id === warehouseId))
      .reduce((sum, s) => sum + Number(s.quantity), 0)
  const reservedFor = (productId: number) =>
    stock
      .filter((s) => s.product_id === productId && (warehouseId === 'all' || s.warehouse_id === warehouseId))
      .reduce((sum, s) => sum + Number(s.reserved), 0)

  function refreshAfterChange() {
    loadProducts()
    refreshCatalog(['products', 'stock']).catch(() => {})
  }

  const activeFilterCount =
    (categoryId !== 'all' ? 1 : 0) +
    (warehouseId !== 'all' ? 1 : 0) +
    (sortMode !== 'name' ? 1 : 0) +
    (inStockOnly ? 1 : 0)

  return (
    <div className={layoutStyles.stack}>
      <div className={layoutStyles.sectionTitle}>
        <h2>{isServices ? 'Услуги' : 'Товары'}</h2>
        <div className={layoutStyles.pageTitleActions}>
          <div className={layoutStyles.pageTitleActionsDesktop}>
            <DropdownMenu
              align="right"
              trigger={
                <Button variant="secondary">
                  <IconDownload size={16} stroke={1.8} /> Экспорт <IconChevronDown size={14} stroke={1.8} />
                </Button>
              }
              items={(Object.keys(EXPORT_FORMAT_LABELS) as ExportFormat[]).map((format) => ({
                key: format,
                label: EXPORT_FORMAT_LABELS[format],
                onSelect: () => handleExport(format),
              }))}
            />
            {canManage && (
              <>
                <DropdownMenu
                  align="right"
                  trigger={
                    <Button variant="secondary">
                      <IconUpload size={16} stroke={1.8} /> Импорт <IconChevronDown size={14} stroke={1.8} />
                    </Button>
                  }
                  items={(Object.keys(IMPORT_FORMAT_LABELS) as ('xlsx' | 'csv')[]).map((format) => ({
                    key: format,
                    label: IMPORT_FORMAT_LABELS[format],
                    onSelect: () => setImportFormat(format),
                  }))}
                />
                <Button onClick={() => navigate(isServices ? '/products/new?kind=service' : '/products/new')}>
                  <IconPlus size={16} stroke={1.8} /> {isServices ? 'Услуга' : 'Товар'}
                </Button>
              </>
            )}
          </div>
          <div className={layoutStyles.pageTitleActionsMobile}>
            <DropdownMenu
              align="right"
              trigger={
                <IconButton variant="muted" size="lg" aria-label="Ещё действия">
                  <IconDots size={20} stroke={1.8} />
                </IconButton>
              }
              items={[
                ...(Object.keys(EXPORT_FORMAT_LABELS) as ExportFormat[]).map((format) => ({
                  key: `export-${format}`,
                  label: `Экспорт: ${EXPORT_FORMAT_LABELS[format]}`,
                  onSelect: () => handleExport(format),
                })),
                ...(canManage
                  ? (Object.keys(IMPORT_FORMAT_LABELS) as ('xlsx' | 'csv')[]).map((format) => ({
                      key: `import-${format}`,
                      label: `Импорт: ${IMPORT_FORMAT_LABELS[format]}`,
                      onSelect: () => setImportFormat(format),
                    }))
                  : []),
              ]}
            />
            {canManage && (
              <IconButton
                variant="accent"
                size="lg"
                aria-label={isServices ? 'Добавить услугу' : 'Добавить товар'}
                onClick={() => navigate(isServices ? '/products/new?kind=service' : '/products/new')}
              >
                <IconPlus size={20} stroke={2} />
              </IconButton>
            )}
          </div>
        </div>
      </div>
      {exportError && <p className={layoutStyles.error}>{exportError}</p>}

      <div className={styles.kindTabs} role="tablist" aria-label="Товары и услуги">
        {KIND_TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={kind === tab.value}
            className={`${styles.kindTab} ${kind === tab.value ? styles.kindTabActive : ''}`}
            onClick={() => {
              const next = new URLSearchParams(searchParams)
              // товар — вид по умолчанию, в адресе его не держим
              if (tab.value === 'product') next.delete('kind')
              else next.set('kind', tab.value)
              setSearchParams(next, { replace: true })
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className={styles.saleSearchPanel}>
        <div className={styles.saleSearchRow}>
          <IconSearch size={16} stroke={1.8} className={styles.saleSearchIcon} />
          <input
            className={styles.saleSearchInput}
            placeholder="Поиск по названию, артикулу…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className={styles.saleFiltersRow}>
          {categories.length > 0 && (
            <label className={layoutStyles.filterField}>
              <Select
                value={categoryId === 'all' ? 'all' : String(categoryId)}
                onChange={(v) => setCategoryId(v === 'all' ? 'all' : Number(v))}
                options={[{ value: 'all', label: 'Все категории' }, ...categoryOptions(categories)]}
              />
            </label>
          )}
          {warehouses.length > 1 && (
            <label className={layoutStyles.filterField}>
              <Select
                value={warehouseId === 'all' ? 'all' : String(warehouseId)}
                onChange={(v) => setWarehouseId(v === 'all' ? 'all' : Number(v))}
                options={[
                  { value: 'all', label: 'Все склады' },
                  ...warehouses.map((w) => ({ value: String(w.id), label: w.name })),
                ]}
              />
            </label>
          )}
          <label className={layoutStyles.filterField}>
            <Select
              value={sortMode}
              onChange={(v) => setSortMode(v as SortMode)}
              options={Object.entries(SORT_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </label>
          <label className={styles.saleCheckbox}>
            <input
              type="checkbox"
              checked={inStockOnly}
              onChange={(e) => setInStockOnly(e.target.checked)}
            />
            Только в наличии
          </label>
          {activeFilterCount > 0 && (
            <ResetFiltersButton
              onClick={() => {
                setCategoryId('all')
                setWarehouseId('all')
                setSortMode('name')
                setInStockOnly(false)
              }}
            />
          )}
        </div>
      </div>

      {error && <p className={layoutStyles.error}>{error}</p>}
      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : products.length === 0 ? (
        <EmptyState
          illustration="empty-shelf"
          title={
            debouncedQuery || activeFilterCount > 0
              ? isServices
                ? 'Услуг не найдено'
                : 'Товаров не найдено'
              : isServices
                ? 'Добавьте первую услугу'
                : 'Добавьте первый товар'
          }
          description={
            debouncedQuery || activeFilterCount > 0
              ? `Измените поиск или сбросьте фильтры — или добавьте ${isServices ? 'новую услугу' : 'новый товар'}.`
              : isServices
                ? 'Услуга продаётся без склада: ремонт, доставка, установка.'
                : 'Без товара нельзя оформить продажу и пройти тур.'
          }
          actionLabel={canManage ? (isServices ? 'Добавить услугу' : 'Добавить товар') : undefined}
          onAction={
            canManage
              ? () => navigate(isServices ? '/products/new?kind=service' : '/products/new')
              : undefined
          }
        />
      ) : (
        <>
          <p className={layoutStyles.textMuted}>
            Показано {products.length} из {total}
          </p>
          <div className={layoutStyles.productGrid}>
            {products.map((p, i) => {
              const qty = stockFor(p.id)
              const reserved = reservedFor(p.id)
              const out = isOutOfStock(qty)
              const low = isLowStock(qty, p.min_stock)
              return (
                <div
                  key={p.id}
                  role="button"
                  tabIndex={0}
                  className={`${layoutStyles.productTile} ${styles.saleHistoryRowIn}`}
                  style={{ '--row-delay': `${Math.min(i, 12) * 25}ms` } as CSSProperties}
                  onClick={() => navigate(`/products/${p.id}`)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      navigate(`/products/${p.id}`)
                    }
                  }}
                >
                  {p.kind === 'service' && !p.photo ? (
                    // без фото у услуги — первая буква названия, как просил
                    // владелец: плашка «нет фото» в списке услуг выглядит мусором
                    <span className={styles.serviceInitial} aria-hidden="true">
                      {p.name.trim().slice(0, 1).toUpperCase()}
                    </span>
                  ) : (
                    <ProductPhoto src={p.photo} />
                  )}
                  <div className={layoutStyles.productTileBody}>
                    <span className={layoutStyles.productTileName}>{p.name}</span>
                    <span className={layoutStyles.productTileMeta}>
                      <span className={layoutStyles.productTilePriceLabel}>Цена за {unitName(p.unit_code)}:</span>
                      <span className={layoutStyles.productTilePrice}>{formatMoney(p.retail_price)} ₽</span>
                    </span>
                    {p.kind === 'service' ? (
                      // у услуги остатка нет — показывать «0 шт» было бы враньём
                      <span className={styles.serviceHint}>Без склада</span>
                    ) : (
                    <span
                      className={`${layoutStyles.productTileStock} ${out ? layoutStyles.productTileStockOut : layoutStyles.productTileStockIn}`}
                    >
                      <span className={layoutStyles.productTileStockLabel}>
                        Остаток:
                        {reserved > 0 && (
                          <InfoHint
                            text={`${formatQuantity(String(reserved))} ${unitName(p.unit_code)} зарезервировано на заказы клиентов и недоступно для продажи — освободится, когда заказ выдадут или отменят.`}
                          />
                        )}
                      </span>
                      <span className={layoutStyles.productTileStockValueWrap}>
                        <span className={layoutStyles.productTileStockValue}>
                          {formatQuantity(String(qty))} {unitName(p.unit_code)}
                        </span>
                        {low && <StockWarningIcon />}
                      </span>
                    </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
          {products.length < total && (
            <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? 'Загрузка…' : `Показать ещё (${total - products.length})`}
            </Button>
          )}
        </>
      )}

      {importFormat && (
        <ImportProductsModal
          format={importFormat}
          onClose={() => setImportFormat(null)}
          onDone={() => {
            setImportFormat(null)
            refreshAfterChange()
          }}
        />
      )}
    </div>
  )
}
