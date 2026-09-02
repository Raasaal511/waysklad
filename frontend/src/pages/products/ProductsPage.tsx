import {
  lazy,
  Suspense,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type ReactNode,
} from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  listProducts,
  createProduct,
  updateProduct,
  createUnit,
  createCategory,
  setProductPhoto,
  exportProducts,
  type Product,
  type Unit,
  type Category,
  type VariantInput,
  type ExportFormat,
} from '../../entities/product/api'
import type { Warehouse } from '../../entities/inventory/api'
import { useCatalog } from '../../app/CatalogContext'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { ImportProductsModal } from './ImportProductsModal'
import {
  IconPlus,
  IconBarcode,
  IconUpload,
  IconDownload,
  IconChevronDown,
  IconTrash,
  IconRefresh,
  IconSearch,
} from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Select } from '../../shared/ui/Select'
import { DropdownMenu } from '../../shared/ui/DropdownMenu'
import { InlinePopover } from '../../shared/ui/InlinePopover'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { StockWarningIcon } from '../../shared/ui/StockWarningIcon'
import { InfoHint } from '../../shared/ui/InfoHint'
import { ResetFiltersButton } from '../../shared/ui/ResetFiltersButton'
import { ProductDetailCard } from '../../shared/ui/ProductDetailCard'
import { isBarcodeScannerSupported } from '../../entities/barcode/barcodeSupport'
import {
  formatMoney,
  formatQuantity,
  isLowStock,
  isOutOfStock,
  normalizeDecimalInput,
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

const BarcodeScanner = lazy(() =>
  import('../../entities/barcode/BarcodeScanner').then((m) => ({ default: m.BarcodeScanner })),
)

const PAGE_SIZE = 50
const PRODUCT_FORM_ID = 'product-form'
const ALLOWED_PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']

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

function generateSku(name: string): string {
  const prefix = name
    .trim()
    .toUpperCase()
    .replace(/[^A-ZА-Я0-9]+/g, '')
    .slice(0, 3)
  const digits = Math.floor(1000 + Math.random() * 9000)
  return prefix ? `${prefix}-${digits}` : String(digits)
}

function categoryOptions(categories: Category[]): { value: string; label: string }[] {
  const result: { value: string; label: string }[] = []
  const visited = new Set<number>()

  function addChildren(parentId: number | null, depth: number) {
    for (const category of categories) {
      if (category.parent_id !== parentId || visited.has(category.id)) continue
      visited.add(category.id)
      result.push({ value: String(category.id), label: `${'— '.repeat(depth)}${category.name}` })
      addChildren(category.id, depth + 1)
    }
  }

  addChildren(null, 0)
  return result
}

export function ProductsPage() {
  const { user } = useAuth()
  const canManage = user?.role === 'owner' || user?.role === 'manager'

  const {
    categories,
    units,
    stock,
    warehouses,
    ensureCategories,
    ensureUnits,
    ensureStock,
    ensureWarehouses,
    ensureProducts,
    refresh: refreshCatalog,
  } = useCatalog()
  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [categoryId, setCategoryId] = useState<number | 'all'>('all')
  const [warehouseId, setWarehouseId] = useState<number | 'all'>('all')
  const [sortMode, setSortMode] = useState<SortMode>('name')
  const [inStockOnly, setInStockOnly] = useState(false)

  const [showForm, setShowForm] = useState(false)
  const [importFormat, setImportFormat] = useState<'xlsx' | 'csv' | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [showEditProduct, setShowEditProduct] = useState(false)
  const [productFormSaving, setProductFormSaving] = useState(false)

  const [searchParams, setSearchParams] = useSearchParams()

  // переход с другой страницы (например «Склады») на карточку конкретного товара
  useEffect(() => {
    const openId = searchParams.get('open')
    if (!openId) return
    ensureProducts()
      .then((all) => {
        const product = all.find((p) => p.id === Number(openId))
        if (product) setSelectedProduct(product)
      })
      .catch(() => {})
      .finally(() => {
        setSearchParams((prev) => {
          const next = new URLSearchParams(prev)
          next.delete('open')
          return next
        })
      })
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

  // Категория и сортировка (кроме "по остатку") считаются на сервере — работают по всему
  // каталогу, а не только по уже подгруженной странице; наличие/остаток остаются
  // клиентскими, т.к. требуют знания складских остатков, которых нет в таблице товаров.
  const serverSort = sortMode === 'stock_desc' ? 'name' : sortMode

  async function loadProducts() {
    setLoading(true)
    setError(null)
    try {
      const { items, total: t } = await listProducts({
        query: debouncedQuery,
        limit: PAGE_SIZE,
        offset: 0,
        categoryId: categoryId === 'all' ? null : categoryId,
        sort: serverSort,
      })
      setProducts(items)
      setTotal(t)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить товары')
    } finally {
      setLoading(false)
    }
  }

  async function loadMore() {
    setLoadingMore(true)
    try {
      const { items, total: t } = await listProducts({
        query: debouncedQuery,
        limit: PAGE_SIZE,
        offset: products.length,
        categoryId: categoryId === 'all' ? null : categoryId,
        sort: serverSort,
      })
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
  }, [debouncedQuery, categoryId, serverSort])

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

  const filtered = useMemo(() => {
    let list = products
    if (inStockOnly) {
      list = list.filter((p) => stockFor(p.id) > 0)
    }
    if (sortMode === 'stock_desc') {
      list = [...list].sort((a, b) => stockFor(b.id) - stockFor(a.id))
    }
    return list
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [products, inStockOnly, sortMode, stock, warehouseId])

  // categories/units не инвалидируем здесь — создание новой категории/юнита уже
  // само вызывает refreshCatalog через onCategoriesChanged/onUnitsChanged ниже,
  // а обычное редактирование товара их не трогает.
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
        <h2>Товары</h2>
        <div className={layoutStyles.row} style={{ gap: 8 }}>
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
              <Button onClick={() => setShowForm(true)}>
                <IconPlus size={16} stroke={1.8} /> Товар
              </Button>
            </>
          )}
        </div>
      </div>
      {exportError && <p className={layoutStyles.error}>{exportError}</p>}

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
      ) : filtered.length === 0 ? (
        <p className={layoutStyles.textMuted}>Товаров не найдено</p>
      ) : (
        <>
          <p className={layoutStyles.textMuted}>
            Показано {filtered.length} из {total}
          </p>
          <div className={layoutStyles.productGrid}>
            {filtered.map((p, i) => {
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
                  onClick={() => setSelectedProduct(p)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setSelectedProduct(p)
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

      {showForm && (
        <Modal
          title="Новый товар"
          onClose={() => setShowForm(false)}
          size="wide"
          footer={
            <Button type="submit" form={PRODUCT_FORM_ID} disabled={productFormSaving}>
              {productFormSaving ? 'Сохранение…' : 'Создать товар'}
            </Button>
          }
        >
          <ProductForm
            product={null}
            categories={categories}
            units={units}
            warehouses={warehouses}
            onCategoriesChanged={() => refreshCatalog(['categories'])}
            onUnitsChanged={() => refreshCatalog(['units'])}
            onSavingChange={setProductFormSaving}
            onDone={() => {
              setShowForm(false)
              refreshAfterChange()
            }}
          />
        </Modal>
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

      {selectedProduct && (
        <ProductDetailCard
          product={selectedProduct}
          categories={categories}
          units={units}
          warehouses={warehouses}
          stock={stock}
          onClose={() => setSelectedProduct(null)}
          onEdit={canManage ? () => setShowEditProduct(true) : undefined}
        />
      )}

      {selectedProduct && showEditProduct && (
        <Modal
          title={`Редактировать: ${selectedProduct.name}`}
          onClose={() => setShowEditProduct(false)}
          size="wide"
          footer={
            <Button type="submit" form={PRODUCT_FORM_ID} disabled={productFormSaving}>
              {productFormSaving ? 'Сохранение…' : 'Сохранить изменения'}
            </Button>
          }
        >
          <ProductForm
            product={selectedProduct}
            categories={categories}
            units={units}
            warehouses={warehouses}
            onCategoriesChanged={() => refreshCatalog(['categories'])}
            onUnitsChanged={() => refreshCatalog(['units'])}
            onSavingChange={setProductFormSaving}
            onDone={(updated) => {
              setShowEditProduct(false)
              setSelectedProduct(updated ?? selectedProduct)
              refreshAfterChange()
            }}
          />
        </Modal>
      )}
    </div>
  )
}

function QuickNewCategoryForm({
  categories,
  open,
  onOpenChange,
  trigger,
  onCreated,
}: {
  categories: Category[]
  open: boolean
  onOpenChange: (open: boolean) => void
  trigger: ReactNode
  onCreated: (category: Category) => void
}) {
  const [name, setName] = useState('')
  const [parentId, setParentId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    e.stopPropagation()
    setError(null)
    setSaving(true)
    try {
      const category = await createCategory({ name, parent_id: parentId })
      setName('')
      setParentId(null)
      onCreated(category)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать категорию')
    } finally {
      setSaving(false)
    }
  }

  return (
    <InlinePopover title="Новая категория" trigger={trigger} open={open} onOpenChange={onOpenChange}>
      <form className={layoutStyles.form} onSubmit={handleSubmit}>
        <label className={layoutStyles.field}>
          Название
          <input value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
        </label>
        <label className={layoutStyles.field}>
          Родительская категория
          <Select
            value={parentId ? String(parentId) : ''}
            onChange={(v) => setParentId(v ? Number(v) : null)}
            options={[{ value: '', label: 'Без родителя' }, ...categoryOptions(categories)]}
          />
        </label>
        {error && <p className={layoutStyles.error}>{error}</p>}
        <Button type="submit" disabled={saving || !name.trim()}>
          {saving ? 'Сохранение…' : 'Создать категорию'}
        </Button>
      </form>
    </InlinePopover>
  )
}

function QuickNewUnitForm({
  open,
  onOpenChange,
  trigger,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  trigger: ReactNode
  onCreated: (unit: Unit) => void
}) {
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [fractional, setFractional] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    e.stopPropagation()
    setError(null)
    setSaving(true)
    try {
      const unit = await createUnit({ code: code.trim(), name: name.trim(), fractional })
      setCode('')
      setName('')
      setFractional(false)
      onCreated(unit)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать единицу измерения')
    } finally {
      setSaving(false)
    }
  }

  return (
    <InlinePopover title="Новая единица измерения" trigger={trigger} open={open} onOpenChange={onOpenChange}>
      <form className={layoutStyles.form} onSubmit={handleSubmit}>
        <label className={layoutStyles.field}>
          Код
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Например, box"
            maxLength={10}
            required
            autoFocus
          />
        </label>
        <label className={layoutStyles.field}>
          Название
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Например, коробка"
            maxLength={50}
            required
          />
        </label>
        <label className={styles.saleCheckbox}>
          <input
            type="checkbox"
            checked={fractional}
            onChange={(e) => setFractional(e.target.checked)}
          />
          Допускает дробное количество (кг, л…)
        </label>
        {error && <p className={layoutStyles.error}>{error}</p>}
        <Button type="submit" disabled={saving || !code.trim() || !name.trim()}>
          {saving ? 'Сохранение…' : 'Создать единицу'}
        </Button>
      </form>
    </InlinePopover>
  )
}

function ProductForm({
  product,
  categories,
  units,
  warehouses,
  onCategoriesChanged,
  onUnitsChanged,
  onSavingChange,
  onDone,
}: {
  product: Product | null
  categories: Category[]
  units: Unit[]
  warehouses: Warehouse[]
  onCategoriesChanged: (category: Category) => void
  onUnitsChanged: (unit: Unit) => void
  onSavingChange?: (saving: boolean) => void
  onDone: (updated?: Product) => void
}) {
  const [name, setName] = useState(product?.name ?? '')
  const [sku, setSku] = useState(product?.sku || (product ? '' : generateSku('')))
  const [barcode, setBarcode] = useState(product?.barcode ?? '')
  const [showScanner, setShowScanner] = useState(false)
  const [unitCode, setUnitCode] = useState(product?.unit_code ?? 'pcs')
  const isFractional = (code: string) => units.find((u) => u.code === code)?.fractional ?? false
  const clampToUnit = (value: string, code: string) => {
    if (value === '' || isFractional(code)) return value
    const num = Number(value)
    return Number.isFinite(num) ? String(Math.floor(num)) : value
  }
  const [purchasePrice, setPurchasePrice] = useState(product?.purchase_price ?? '')
  const [retailPrice, setRetailPrice] = useState(product?.retail_price ?? '')
  const [minStock, setMinStock] = useState(
    clampToUnit(product?.min_stock ? String(Number(product.min_stock)) : '', product?.unit_code ?? 'pcs'),
  )
  const [categoryId, setCategoryId] = useState<number | null>(product?.category_id ?? null)
  const [showNewCategory, setShowNewCategory] = useState(false)
  const [showNewUnit, setShowNewUnit] = useState(false)
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(product?.photo || null)
  const [photoError, setPhotoError] = useState<string | null>(null)
  const [createdProduct, setCreatedProduct] = useState<Product | null>(null)
  const photoInputRef = useRef<HTMLInputElement>(null)
  const [variants, setVariants] = useState<VariantInput[]>(
    product?.variants.map((v) => ({ id: v.id, size: v.size, color: v.color, barcode: v.barcode })) ?? [],
  )
  const [initialStockWarehouseId, setInitialStockWarehouseId] = useState<number | null>(
    warehouses[0]?.id ?? null,
  )
  const [initialStockQuantity, setInitialStockQuantity] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  function handlePhotoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null
    if (file && !ALLOWED_PHOTO_TYPES.includes(file.type)) {
      setPhotoError('Неподдерживаемый формат файла. Загрузите изображение JPG, PNG, WEBP или GIF.')
      e.target.value = ''
      return
    }
    setPhotoError(null)
    setPhotoFile(file)
    setPhotoPreview(file ? URL.createObjectURL(file) : product?.photo || null)
  }

  function handleRemovePhoto() {
    setPhotoFile(null)
    setPhotoError(null)
    setPhotoPreview(product?.photo || null)
    if (photoInputRef.current) photoInputRef.current.value = ''
  }

  function addVariant() {
    setVariants((v) => [...v, { size: '', color: '' }])
  }

  function updateVariant(index: number, patch: Partial<VariantInput>) {
    setVariants((v) => v.map((item, i) => (i === index ? { ...item, ...patch } : item)))
  }

  function removeVariant(index: number) {
    setVariants((v) => v.filter((_, i) => i !== index))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    onSavingChange?.(true)
    try {
      const payload = {
        name,
        sku,
        barcode: barcode || null,
        unit_code: unitCode,
        purchase_price: purchasePrice || '0',
        retail_price: retailPrice || '0',
        min_stock: minStock || '0',
        category_id: categoryId,
        variants,
      }
      let saved: Product
      if (product) {
        saved = await updateProduct(product.id, { ...payload, photo: product.photo })
      } else if (createdProduct) {
        // Товар уже был создан на предыдущей попытке (упала только загрузка фото) —
        // повторно создавать запись нельзя, иначе получится дубликат.
        saved = await updateProduct(createdProduct.id, { ...payload, photo: createdProduct.photo })
      } else {
        saved = await createProduct({
          ...payload,
          initial_stock_warehouse_id: initialStockQuantity ? initialStockWarehouseId : null,
          initial_stock_quantity: initialStockQuantity || null,
        })
        setCreatedProduct(saved)
      }
      if (photoFile) {
        saved = await setProductPhoto(saved.id, photoFile)
      }
      onDone(saved)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить товар')
    } finally {
      setSaving(false)
      onSavingChange?.(false)
    }
  }

  return (
    <form className={layoutStyles.form} id={PRODUCT_FORM_ID} onSubmit={handleSubmit}>
    <fieldset className={styles.formFieldset} disabled={saving}>
      <label className={layoutStyles.field}>
        Название
        <input value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
      </label>

      <div className={layoutStyles.row}>
        <label className={layoutStyles.field} style={{ flex: 1 }}>
          Закупочная цена
          <input
            type="text"
            inputMode="decimal"
            value={purchasePrice}
            onChange={(e) => {
              const normalized = normalizeDecimalInput(e.target.value)
              if (normalized !== null) setPurchasePrice(normalized)
            }}
          />
        </label>
        <label className={layoutStyles.field} style={{ flex: 1 }}>
          Розничная цена
          <input
            type="text"
            inputMode="decimal"
            value={retailPrice}
            onChange={(e) => {
              const normalized = normalizeDecimalInput(e.target.value)
              if (normalized !== null) setRetailPrice(normalized)
            }}
          />
        </label>
      </div>

      <label className={layoutStyles.field}>
        Категория
        <div className={layoutStyles.row}>
          <div style={{ flex: 1 }}>
            <Select
              value={categoryId ? String(categoryId) : ''}
              onChange={(v) => setCategoryId(v ? Number(v) : null)}
              options={[{ value: '', label: 'Без категории' }, ...categoryOptions(categories)]}
            />
          </div>
          <QuickNewCategoryForm
            categories={categories}
            open={showNewCategory}
            onOpenChange={setShowNewCategory}
            trigger={
              <Button variant="secondary" onClick={() => setShowNewCategory(true)}>
                <IconPlus size={16} stroke={1.8} />
              </Button>
            }
            onCreated={(category) => {
              onCategoriesChanged(category)
              setCategoryId(category.id)
              setShowNewCategory(false)
            }}
          />
        </div>
      </label>

      <h4 className={styles.formSectionTitle}>Учёт и остаток</h4>

      <label className={layoutStyles.field}>
        Единица измерения
        <div className={layoutStyles.row}>
          <div style={{ flex: 1 }}>
            <Select
              value={unitCode}
              onChange={(code) => {
                setUnitCode(code)
                setMinStock((v) => clampToUnit(v, code))
                setInitialStockQuantity((v) => clampToUnit(v, code))
              }}
              options={
                units.length === 0
                  ? [{ value: unitCode, label: unitCode }]
                  : units.map((u) => ({ value: u.code, label: u.name }))
              }
            />
          </div>
          <QuickNewUnitForm
            open={showNewUnit}
            onOpenChange={setShowNewUnit}
            trigger={
              <Button variant="secondary" onClick={() => setShowNewUnit(true)}>
                <IconPlus size={16} stroke={1.8} />
              </Button>
            }
            onCreated={(unit) => {
              onUnitsChanged(unit)
              setUnitCode(unit.code)
              setShowNewUnit(false)
            }}
          />
        </div>
      </label>

      {!product && warehouses.length > 0 && (
        <div className={layoutStyles.row}>
          <label className={layoutStyles.field} style={{ flex: 1 }}>
            Начальный остаток
            <input
              type="text"
              inputMode="decimal"
              value={initialStockQuantity}
              onChange={(e) => {
                const normalized = normalizeDecimalInput(e.target.value)
                if (normalized !== null) setInitialStockQuantity(normalized)
              }}
              onBlur={() => setInitialStockQuantity((v) => clampToUnit(v, unitCode))}
              placeholder="0 — если ещё не завезли"
            />
          </label>
          {warehouses.length > 1 && (
            <label className={layoutStyles.field} style={{ flex: 1 }}>
              На каком складе
              <Select
                value={String(initialStockWarehouseId ?? '')}
                onChange={(v) => setInitialStockWarehouseId(Number(v))}
                options={warehouses.map((w) => ({ value: String(w.id), label: w.name }))}
              />
            </label>
          )}
        </div>
      )}

      <label className={layoutStyles.field}>
        Минимальный остаток
        <span className={layoutStyles.fieldHint}>Порог, при котором товар считается «заканчивается» — не текущее количество</span>
        <input
          type="text"
          inputMode="decimal"
          value={minStock}
          onChange={(e) => {
            const normalized = normalizeDecimalInput(e.target.value)
            if (normalized !== null) setMinStock(normalized)
          }}
          onBlur={() => setMinStock((v) => clampToUnit(v, unitCode))}
        />
      </label>

      <h4 className={styles.formSectionTitle}>Идентификация</h4>

      <label className={layoutStyles.field}>
        Артикул
        <div className={layoutStyles.row}>
          <input value={sku} onChange={(e) => setSku(e.target.value)} style={{ flex: 1 }} />
          <IconButton
            variant="neutral"
            onClick={() => setSku(generateSku(name))}
            aria-label="Сгенерировать артикул заново"
            tooltip="Сгенерировать заново"
          >
            <IconRefresh size={16} stroke={1.8} />
          </IconButton>
        </div>
      </label>
      <label className={layoutStyles.field}>
        Штрихкод
        <div className={layoutStyles.row}>
          <input
            value={barcode ?? ''}
            onChange={(e) => setBarcode(e.target.value)}
            placeholder="Отсканируйте или введите вручную"
            style={{ flex: 1 }}
          />
          {isBarcodeScannerSupported() && (
            <Button variant="secondary" onClick={() => setShowScanner(true)}>
              <IconBarcode size={16} stroke={1.8} />
            </Button>
          )}
        </div>
      </label>
      {showScanner && (
        <Modal title="Сканировать штрихкод" onClose={() => setShowScanner(false)}>
          <Suspense fallback={<p className={layoutStyles.textMuted}>Загрузка сканера…</p>}>
            <BarcodeScanner
              onDetected={(code) => {
                setBarcode(code)
                setShowScanner(false)
              }}
              onClose={() => setShowScanner(false)}
            />
          </Suspense>
        </Modal>
      )}

      <h4 className={styles.formSectionTitle}>Дополнительно</h4>

      <label className={layoutStyles.field}>
        Фото
        <input ref={photoInputRef} type="file" accept="image/*" onChange={handlePhotoChange} />
      </label>
      {photoError && <p className={layoutStyles.error}>{photoError}</p>}
      {photoPreview && (
        <div className={styles.productFormPhotoPreviewWrap}>
          <img src={photoPreview} alt="" className={styles.productFormPhotoPreview} />
          <IconButton
            type="button"
            variant="danger"
            className={styles.productFormPhotoRemove}
            onClick={handleRemovePhoto}
            aria-label="Убрать фото"
          >
            <IconTrash size={14} stroke={1.8} />
          </IconButton>
        </div>
      )}

      <div className={layoutStyles.field}>
        <div className={`${layoutStyles.row} ${layoutStyles.between}`}>
          <span>Варианты (размер/цвет)</span>
          <Button variant="secondary" onClick={addVariant}>
            <IconPlus size={14} stroke={1.8} /> Добавить
          </Button>
        </div>
        {variants.length > 0 && (
          <div className={styles.variantList}>
            <div className={`${styles.variantRow} ${styles.variantRowHeader}`}>
              <span>Размер</span>
              <span>Цвет</span>
              <span />
            </div>
            {variants.map((v, i) => (
              <div key={i} className={styles.variantRow}>
                <input
                  value={v.size}
                  onChange={(e) => updateVariant(i, { size: e.target.value })}
                />
                <input
                  value={v.color}
                  onChange={(e) => updateVariant(i, { color: e.target.value })}
                />
                <IconButton variant="danger" onClick={() => removeVariant(i)} aria-label="Удалить вариант">
                  <IconTrash size={16} stroke={1.8} />
                </IconButton>
              </div>
            ))}
          </div>
        )}
      </div>

      {error && <p className={layoutStyles.error}>{error}</p>}
    </fieldset>
    </form>
  )
}
