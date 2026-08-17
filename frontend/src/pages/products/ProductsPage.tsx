import { lazy, Suspense, useEffect, useMemo, useState, type CSSProperties, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  listProducts,
  listAllProducts,
  createProduct,
  updateProduct,
  listUnits,
  createUnit,
  listCategories,
  createCategory,
  setProductPhoto,
  importProducts,
  exportProducts,
  type Product,
  type Unit,
  type Category,
  type VariantInput,
  type ExportFormat,
} from '../../entities/product/api'
import { listWarehouses, listStock, type Warehouse, type StockItem } from '../../entities/inventory/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import {
  IconPlus,
  IconBarcode,
  IconUpload,
  IconDownload,
  IconChevronDown,
  IconTrash,
  IconRefresh,
} from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Select } from '../../shared/ui/Select'
import { DropdownMenu } from '../../shared/ui/DropdownMenu'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { StockWarningIcon } from '../../shared/ui/StockWarningIcon'
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
const IMPORT_ERRORS_COLUMNS = '100px 1fr'

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

  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [categories, setCategories] = useState<Category[]>([])
  const [units, setUnits] = useState<Unit[]>([])
  const [stock, setStock] = useState<StockItem[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [categoryId, setCategoryId] = useState<number | 'all'>('all')
  const [sortMode, setSortMode] = useState<SortMode>('name')
  const [inStockOnly, setInStockOnly] = useState(false)

  const [showForm, setShowForm] = useState(false)
  const [importFormat, setImportFormat] = useState<'xlsx' | 'csv' | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [showEditProduct, setShowEditProduct] = useState(false)

  const [searchParams, setSearchParams] = useSearchParams()

  // переход с другой страницы (например «Склады») на карточку конкретного товара
  useEffect(() => {
    const openId = searchParams.get('open')
    if (!openId) return
    listAllProducts()
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
    listCategories().then(setCategories).catch(() => {})
    listUnits().then(setUnits).catch(() => {})
    listStock().then(setStock).catch(() => {})
    listWarehouses().then(setWarehouses).catch(() => {})
  }, [])

  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code
  const stockFor = (productId: number) =>
    stock.filter((s) => s.product_id === productId).reduce((sum, s) => sum + Number(s.quantity), 0)

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
  }, [products, inStockOnly, sortMode, stock])

  function refreshAfterChange() {
    loadProducts()
  }

  const activeFilterCount =
    (categoryId !== 'all' ? 1 : 0) + (sortMode !== 'name' ? 1 : 0) + (inStockOnly ? 1 : 0)

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Товары</h2>
        <div className="row" style={{ gap: 8 }}>
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
      {exportError && <p className="error">{exportError}</p>}

      <div className="sale-search-panel">
        <div className="sale-search-row">
          <input
            className="sale-search-input"
            placeholder="Поиск по названию, артикулу…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="sale-filters-row">
          {categories.length > 0 && (
            <label className="filter-field">
              <Select
                value={categoryId === 'all' ? 'all' : String(categoryId)}
                onChange={(v) => setCategoryId(v === 'all' ? 'all' : Number(v))}
                options={[{ value: 'all', label: 'Все категории' }, ...categoryOptions(categories)]}
              />
            </label>
          )}
          <label className="filter-field">
            <Select
              value={sortMode}
              onChange={(v) => setSortMode(v as SortMode)}
              options={Object.entries(SORT_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </label>
          <label className="sale-checkbox">
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
                setSortMode('name')
                setInStockOnly(false)
              }}
            />
          )}
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : filtered.length === 0 ? (
        <p className="text-muted">Товаров не найдено</p>
      ) : (
        <>
          <p className="text-muted">
            Показано {filtered.length} из {total}
          </p>
          <div className="product-grid">
            {filtered.map((p, i) => {
              const qty = stockFor(p.id)
              const out = isOutOfStock(qty)
              const low = isLowStock(qty, p.min_stock)
              return (
                <div
                  key={p.id}
                  role="button"
                  tabIndex={0}
                  className="product-tile sale-history-row-in"
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
                  <div className="product-tile-body">
                    <span className="product-tile-name">{p.name}</span>
                    <span className="product-tile-meta">
                      <span className="product-tile-price-label">Цена за {unitName(p.unit_code)}:</span>
                      <span className="product-tile-price">{formatMoney(p.retail_price)} ₽</span>
                    </span>
                    <span
                      className={`product-tile-stock${out ? ' product-tile-stock-out' : ' product-tile-stock-in'}`}
                    >
                      <span className="product-tile-stock-label">Остаток:</span>
                      <span className="product-tile-stock-value-wrap">
                        <span className="product-tile-stock-value">
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
        <Modal title="Новый товар" onClose={() => setShowForm(false)} size="wide">
          <ProductForm
            product={null}
            categories={categories}
            units={units}
            warehouses={warehouses}
            onCategoriesChanged={setCategories}
            onUnitsChanged={setUnits}
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
        >
          <ProductForm
            product={selectedProduct}
            categories={categories}
            units={units}
            warehouses={warehouses}
            onCategoriesChanged={setCategories}
            onUnitsChanged={setUnits}
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

function ImportProductsModal({
  format,
  onClose,
  onDone,
}: {
  format: 'xlsx' | 'csv'
  onClose: () => void
  onDone: () => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<{ created: number; errors: { row: number; message: string }[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [importing, setImporting] = useState(false)

  async function handleImport() {
    if (!file) return
    setError(null)
    setImporting(true)
    try {
      const res = await importProducts(file)
      setResult(res)
      if (res.errors.length === 0) {
        onDone()
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось импортировать товары')
    } finally {
      setImporting(false)
    }
  }

  return (
    <Modal title={`Импорт товаров из ${format === 'csv' ? 'CSV' : 'Excel'}`} onClose={onClose}>
      <div className="stack">
        <p className="text-muted">
          Формат колонок: Название | Артикул | Штрихкод | Ед.изм. | Закупочная цена | Розничная
          цена | Мин.остаток. Первая строка — заголовок, пропускается.
        </p>
        <input
          type="file"
          accept={format === 'csv' ? '.csv' : '.xlsx'}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        {error && <p className="error">{error}</p>}
        {result && (
          <div className="stack">
            <p>Создано товаров: {result.created}</p>
            {result.errors.length > 0 && (
              <div className="data-table">
                <div className="data-table-head" style={{ gridTemplateColumns: IMPORT_ERRORS_COLUMNS }}>
                  <span>Строка</span>
                  <span>Ошибка</span>
                </div>
                <div className="data-table-body">
                  {result.errors.map((e, i) => (
                    <div key={i} className="data-row" style={{ gridTemplateColumns: IMPORT_ERRORS_COLUMNS }}>
                      <span>{e.row}</span>
                      <span className="text-muted">{e.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        <div className="row" style={{ gap: 8 }}>
          <Button onClick={handleImport} disabled={!file || importing}>
            {importing ? 'Импорт…' : 'Импортировать'}
          </Button>
          {result && (
            <Button variant="secondary" onClick={onClose}>
              Готово
            </Button>
          )}
        </div>
      </div>
    </Modal>
  )
}

function QuickNewCategoryForm({
  categories,
  onCreated,
  onClose,
}: {
  categories: Category[]
  onCreated: (category: Category) => void
  onClose: () => void
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
      onCreated(category)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать категорию')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Новая категория" onClose={onClose}>
      <form className="form" onSubmit={handleSubmit}>
        <label className="field">
          Название
          <input value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
        </label>
        <label className="field">
          Родительская категория
          <Select
            value={parentId ? String(parentId) : ''}
            onChange={(v) => setParentId(v ? Number(v) : null)}
            options={[{ value: '', label: 'Без родителя' }, ...categoryOptions(categories)]}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <Button type="submit" disabled={saving || !name.trim()}>
          {saving ? 'Сохранение…' : 'Создать категорию'}
        </Button>
      </form>
    </Modal>
  )
}

function QuickNewUnitForm({
  onCreated,
  onClose,
}: {
  onCreated: (unit: Unit) => void
  onClose: () => void
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
      onCreated(unit)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать единицу измерения')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Новая единица измерения" onClose={onClose}>
      <form className="form" onSubmit={handleSubmit}>
        <label className="field">
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
        <label className="field">
          Название
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Например, коробка"
            maxLength={50}
            required
          />
        </label>
        <label className="sale-checkbox">
          <input
            type="checkbox"
            checked={fractional}
            onChange={(e) => setFractional(e.target.checked)}
          />
          Допускает дробное количество (кг, л…)
        </label>
        {error && <p className="error">{error}</p>}
        <Button type="submit" disabled={saving || !code.trim() || !name.trim()}>
          {saving ? 'Сохранение…' : 'Создать единицу'}
        </Button>
      </form>
    </Modal>
  )
}

function ProductForm({
  product,
  categories,
  units,
  warehouses,
  onCategoriesChanged,
  onUnitsChanged,
  onDone,
}: {
  product: Product | null
  categories: Category[]
  units: Unit[]
  warehouses: Warehouse[]
  onCategoriesChanged: (categories: Category[]) => void
  onUnitsChanged: (units: Unit[]) => void
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
    setPhotoFile(file)
    if (file) setPhotoPreview(URL.createObjectURL(file))
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
      } else {
        saved = await createProduct({
          ...payload,
          initial_stock_warehouse_id: initialStockQuantity ? initialStockWarehouseId : null,
          initial_stock_quantity: initialStockQuantity || null,
        })
      }
      if (photoFile) {
        saved = await setProductPhoto(saved.id, photoFile)
      }
      onDone(saved)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить товар')
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
        Артикул
        <div className="row">
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
      <label className="field">
        Штрихкод
        <div className="row">
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
          <Suspense fallback={<p className="text-muted">Загрузка сканера…</p>}>
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
      <label className="field">
        Единица измерения
        <div className="row">
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
          <Button variant="secondary" onClick={() => setShowNewUnit(true)}>
            <IconPlus size={16} stroke={1.8} />
          </Button>
        </div>
      </label>
      {showNewUnit && (
        <QuickNewUnitForm
          onClose={() => setShowNewUnit(false)}
          onCreated={(unit) => {
            onUnitsChanged([...units, unit])
            setUnitCode(unit.code)
            setShowNewUnit(false)
          }}
        />
      )}
      <div className="row">
        <label className="field" style={{ flex: 1 }}>
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
        <label className="field" style={{ flex: 1 }}>
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
      {!product && warehouses.length > 0 && (
        <div className="field-group">
          <span className="field-group-title">Сколько товара есть сейчас</span>
          <div className="row">
            <label className="field" style={{ flex: 1 }}>
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
              <label className="field" style={{ flex: 1 }}>
                На каком складе
                <Select
                  value={String(initialStockWarehouseId ?? '')}
                  onChange={(v) => setInitialStockWarehouseId(Number(v))}
                  options={warehouses.map((w) => ({ value: String(w.id), label: w.name }))}
                />
              </label>
            )}
          </div>
        </div>
      )}

      <label className="field">
        Минимальный остаток
        <span className="field-hint">Порог, при котором товар считается «заканчивается» — не текущее количество</span>
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

      <label className="field">
        Категория
        <div className="row">
          <div style={{ flex: 1 }}>
            <Select
              value={categoryId ? String(categoryId) : ''}
              onChange={(v) => setCategoryId(v ? Number(v) : null)}
              options={[{ value: '', label: 'Без категории' }, ...categoryOptions(categories)]}
            />
          </div>
          <Button variant="secondary" onClick={() => setShowNewCategory(true)}>
            <IconPlus size={16} stroke={1.8} />
          </Button>
        </div>
      </label>
      {showNewCategory && (
        <QuickNewCategoryForm
          categories={categories}
          onClose={() => setShowNewCategory(false)}
          onCreated={(category) => {
            onCategoriesChanged([...categories, category])
            setCategoryId(category.id)
            setShowNewCategory(false)
          }}
        />
      )}

      <label className="field">
        Фото
        <input type="file" accept="image/*" onChange={handlePhotoChange} />
      </label>
      {photoPreview && <img src={photoPreview} alt="" className="product-form-photo-preview" />}

      <div className="field">
        <div className="row between">
          <span>Варианты (размер/цвет)</span>
          <Button variant="secondary" onClick={addVariant}>
            <IconPlus size={14} stroke={1.8} /> Добавить
          </Button>
        </div>
        {variants.length > 0 && (
          <div className="variant-list">
            <div className="variant-row variant-row-header">
              <span>Размер</span>
              <span>Цвет</span>
              <span />
            </div>
            {variants.map((v, i) => (
              <div key={i} className="variant-row">
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

      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : product ? 'Сохранить изменения' : 'Создать товар'}
      </Button>
    </form>
  )
}
