import {
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
} from 'react'
import {
  createProduct,
  updateProduct,
  createUnit,
  createCategory,
  setProductPhoto,
  type Product,
  type Unit,
  type Category,
  type VariantInput,
} from '../../entities/product/api'
import { createWarehouse, type Warehouse } from '../../entities/inventory/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import {
  IconPlus,
  IconBarcode,
  IconTrash,
  IconRefresh,
  IconPhoto,
  IconX,
  IconPackage,
  IconCoin,
  IconAlertTriangle,
  IconShoppingBag,
  IconCheck,
} from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { CreatableSelect } from '../../shared/ui/CreatableSelect'
import { isBarcodeScannerSupported } from '../../entities/barcode/barcodeSupport'
import { formatMoney, normalizeDecimalInput } from '../../shared/lib/format'
import layoutStyles from '../../shared/ui/Layout.module.css'
import detail from './ProductDetailPage.module.css'
import styles from './ProductForm.module.css'

const BarcodeScanner = lazy(() =>
  import('../../entities/barcode/BarcodeScanner').then((m) => ({ default: m.BarcodeScanner })),
)

const ALLOWED_PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']

export function generateSku(name: string): string {
  const prefix = name
    .trim()
    .toUpperCase()
    .replace(/[^A-ZА-Я0-9]+/g, '')
    .slice(0, 3)
  const digits = Math.floor(1000 + Math.random() * 9000)
  return prefix ? `${prefix}-${digits}` : String(digits)
}

export function categoryOptions(categories: Category[]): { value: string; label: string }[] {
  const result: { value: string; label: string }[] = []
  const visited = new Set<number>()

  function addChildren(parentId: number | null, depth: number) {
    for (const category of categories) {
      if (category.parent_id !== parentId || visited.has(category.id)) continue
      visited.add(category.id)
      result.push({
        value: String(category.id),
        label: `${'— '.repeat(depth)}${category.name}`,
        searchText: category.name,
      })
      addChildren(category.id, depth + 1)
    }
  }

  addChildren(null, 0)
  return result
}

const CYR_TO_LAT: Record<string, string> = {
  а: 'a',
  б: 'b',
  в: 'v',
  г: 'g',
  д: 'd',
  е: 'e',
  ё: 'e',
  ж: 'zh',
  з: 'z',
  и: 'i',
  й: 'y',
  к: 'k',
  л: 'l',
  м: 'm',
  н: 'n',
  о: 'o',
  п: 'p',
  р: 'r',
  с: 's',
  т: 't',
  у: 'u',
  ф: 'f',
  х: 'h',
  ц: 'ts',
  ч: 'ch',
  ш: 'sh',
  щ: 'sch',
  ъ: '',
  ы: 'y',
  ь: '',
  э: 'e',
  ю: 'yu',
  я: 'ya',
}

const FRACTIONAL_UNIT_NAMES = new Set([
  'кг',
  'г',
  'л',
  'мл',
  'м',
  'м²',
  'м2',
  'м³',
  'м3',
  'kg',
  'g',
  'l',
  'ml',
  'm',
])

function suggestUnitCode(name: string, existingCodes: string[]): string {
  const slug = name
    .trim()
    .toLowerCase()
    .split('')
    .map((ch) => CYR_TO_LAT[ch] ?? ch)
    .join('')
    .replace(/[^a-z0-9]+/g, '')
    .slice(0, 8)
  const base = slug || 'u'
  const taken = new Set(existingCodes)
  if (!taken.has(base)) return base
  for (let i = 2; i < 1000; i++) {
    const suffix = String(i)
    const candidate = `${base.slice(0, 10 - suffix.length)}${suffix}`
    if (!taken.has(candidate)) return candidate
  }
  return `u${Date.now().toString(36).slice(-9)}`
}

function toCreateError(err: unknown, fallback: string): Error {
  return new Error(err instanceof ApiError ? err.message : fallback)
}

export function ProductForm({
  product,
  categories,
  units,
  warehouses,
  onCategoriesChanged,
  onUnitsChanged,
  onWarehousesChanged,
  onSavingChange,
  onDone,
  submitLabel,
}: {
  product: Product | null
  categories: Category[]
  units: Unit[]
  warehouses: Warehouse[]
  onCategoriesChanged: () => void | Promise<void>
  onUnitsChanged: () => void | Promise<void>
  onWarehousesChanged: () => void | Promise<void>
  onSavingChange?: (saving: boolean) => void
  onDone: (updated?: Product) => void
  submitLabel?: string
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
  const [photoFile, setPhotoFile] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(product?.photo || null)
  const [photoError, setPhotoError] = useState<string | null>(null)
  const [photoDragActive, setPhotoDragActive] = useState(false)
  const [createdProduct, setCreatedProduct] = useState<Product | null>(null)
  const photoInputRef = useRef<HTMLInputElement>(null)
  const [variants, setVariants] = useState<VariantInput[]>(
    product?.variants.map((v) => ({ id: v.id, size: v.size, color: v.color, barcode: v.barcode })) ?? [],
  )
  const [initialStockWarehouseId, setInitialStockWarehouseId] = useState<number | null>(
    warehouses[0]?.id ?? null,
  )
  const [initialStockQuantity, setInitialStockQuantity] = useState('')
  const [showOnStorefront, setShowOnStorefront] = useState(product?.show_on_storefront ?? false)
  const [storefrontMinQty, setStorefrontMinQty] = useState(product?.storefront_min_qty ?? '')
  const [storefrontStepQty, setStorefrontStepQty] = useState(product?.storefront_step_qty ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!product && initialStockWarehouseId == null && warehouses[0]) {
      setInitialStockWarehouseId(warehouses[0].id)
    }
  }, [product, initialStockWarehouseId, warehouses])

  const unitLabel = units.find((u) => u.code === unitCode)?.name ?? unitCode
  const liveMargin =
    purchasePrice !== '' && retailPrice !== '' && Number.isFinite(Number(purchasePrice)) && Number.isFinite(Number(retailPrice))
      ? String(Number(retailPrice) - Number(purchasePrice))
      : null

  function applyPhotoFile(file: File | null) {
    if (file && !ALLOWED_PHOTO_TYPES.includes(file.type)) {
      setPhotoError('Неподдерживаемый формат файла. Загрузите изображение JPG, PNG, WEBP или GIF.')
      if (photoInputRef.current) photoInputRef.current.value = ''
      return
    }
    setPhotoError(null)
    setPhotoFile(file)
    setPhotoPreview(file ? URL.createObjectURL(file) : product?.photo || null)
  }

  function handleRemovePhoto() {
    setPhotoFile(null)
    setPhotoError(null)
    setPhotoPreview(null)
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

  async function handleCreateCategory(query: string) {
    try {
      const category = await createCategory({ name: query.slice(0, 200) })
      await onCategoriesChanged()
      setCategoryId(category.id)
    } catch (err) {
      throw toCreateError(err, 'Не удалось создать категорию')
    }
  }

  async function handleCreateUnit(query: string) {
    try {
      const name = query.slice(0, 50)
      const code = suggestUnitCode(name, units.map((u) => u.code))
      const unit = await createUnit({
        code,
        name,
        fractional: FRACTIONAL_UNIT_NAMES.has(name.trim().toLowerCase()),
      })
      await onUnitsChanged()
      setUnitCode(unit.code)
      setMinStock((v) => clampToUnit(v, unit.code))
      setInitialStockQuantity((v) => clampToUnit(v, unit.code))
    } catch (err) {
      throw toCreateError(err, 'Не удалось создать единицу измерения')
    }
  }

  async function handleCreateWarehouse(query: string) {
    try {
      const warehouse = await createWarehouse({ name: query.slice(0, 200) })
      await onWarehousesChanged()
      setInitialStockWarehouseId(warehouse.id)
    } catch (err) {
      throw toCreateError(err, 'Не удалось создать склад')
    }
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
        show_on_storefront: showOnStorefront,
        storefront_min_qty: storefrontMinQty || null,
        storefront_step_qty: storefrontStepQty || null,
        variants,
      }
      let saved: Product
      if (product) {
        saved = await updateProduct(product.id, {
          ...payload,
          photo: photoFile ? product.photo : photoPreview || '',
        })
      } else if (createdProduct) {
        saved = await updateProduct(createdProduct.id, {
          ...payload,
          photo: photoFile ? createdProduct.photo : photoPreview || '',
        })
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
    <form className={styles.editForm} onSubmit={handleSubmit}>
      <fieldset className={styles.formFieldset} disabled={saving}>
        <section
          className={`${detail.hero} ${detail.heroWithMedia} ${styles.heroEdit} ${detail.reveal}`}
          style={{ '--reveal-delay': '0ms' } as CSSProperties}
        >
          <div
            className={[
              detail.heroPhoto,
              styles.heroPhotoDrop,
              photoDragActive ? styles.heroPhotoDropActive : '',
              !photoPreview ? detail.heroPhotoEmpty : '',
            ]
              .filter(Boolean)
              .join(' ')}
            onClick={() => photoInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                photoInputRef.current?.click()
              }
            }}
            onDragOver={(e) => {
              e.preventDefault()
              setPhotoDragActive(true)
            }}
            onDragLeave={() => setPhotoDragActive(false)}
            onDrop={(e) => {
              e.preventDefault()
              setPhotoDragActive(false)
              applyPhotoFile(e.dataTransfer.files?.[0] ?? null)
            }}
            role="button"
            tabIndex={0}
            aria-label="Выбрать или перетащить фото товара"
          >
            <input
              ref={photoInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              className={styles.hiddenFile}
              onChange={(e) => applyPhotoFile(e.target.files?.[0] ?? null)}
            />
            {photoPreview ? (
              <>
                <img src={photoPreview} alt="" className={styles.heroPhotoImg} />
                <div className={styles.heroPhotoOverlay}>
                  <span>Заменить</span>
                  <button
                    type="button"
                    className={styles.heroPhotoClear}
                    aria-label="Убрать фото"
                    onClick={(e) => {
                      e.stopPropagation()
                      handleRemovePhoto()
                    }}
                  >
                    <IconX size={14} stroke={1.8} />
                  </button>
                </div>
              </>
            ) : (
              <div className={styles.heroPhotoPlaceholder}>
                <IconPhoto size={40} stroke={1.4} />
                <span>Фото</span>
                <small>перетащите или выберите</small>
              </div>
            )}
          </div>

          <div className={detail.heroBody}>
            <div className={detail.heroTop}>
              <div className={detail.heroHeading}>
                <input
                  className={`${detail.heroTitle} ${styles.titleInput}`}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Название товара"
                  required
                  autoFocus
                />
                <div className={detail.heroTags}>
                  <div className={styles.tagSelect}>
                    <CreatableSelect
                      value={categoryId ? String(categoryId) : ''}
                      onChange={(v) => setCategoryId(v ? Number(v) : null)}
                      options={[{ value: '', label: 'Без категории' }, ...categoryOptions(categories)]}
                      onCreate={handleCreateCategory}
                      searchPlaceholder="Категория…"
                      createLabel={(q) => `Создать «${q}»`}
                      aria-label="Категория"
                    />
                  </div>
                  <label className={styles.skuEdit}>
                    <span className={detail.skuChip}>Арт.</span>
                    <input value={sku} onChange={(e) => setSku(e.target.value)} placeholder="артикул" />
                    <IconButton
                      type="button"
                      variant="muted"
                      onClick={() => setSku(generateSku(name))}
                      aria-label="Сгенерировать артикул"
                      tooltip="Сгенерировать"
                    >
                      <IconRefresh size={14} stroke={1.8} />
                    </IconButton>
                  </label>
                  {showOnStorefront && (
                    <span className={detail.storefrontChip}>
                      <IconShoppingBag size={13} stroke={1.8} /> На витрине
                    </span>
                  )}
                </div>
              </div>
            </div>

            <label className={styles.priceEdit}>
              <input
                className={detail.heroPrice}
                type="text"
                inputMode="decimal"
                value={retailPrice}
                onChange={(e) => {
                  const normalized = normalizeDecimalInput(e.target.value)
                  if (normalized !== null) setRetailPrice(normalized)
                }}
                placeholder="0"
              />
              <span className={styles.priceSuffix}>₽</span>
            </label>

            <div className={`${detail.heroMeta} ${styles.metaEdit}`}>
              <label className={styles.metaField}>
                <IconBarcode size={15} stroke={1.8} />
                <input
                  value={barcode ?? ''}
                  onChange={(e) => setBarcode(e.target.value)}
                  placeholder="Штрихкод"
                />
                {isBarcodeScannerSupported() && (
                  <IconButton
                    type="button"
                    variant="muted"
                    onClick={() => setShowScanner(true)}
                    aria-label="Сканировать штрихкод"
                    tooltip="Сканер"
                  >
                    <IconBarcode size={16} stroke={1.8} />
                  </IconButton>
                )}
              </label>
              <div className={styles.metaFieldSelect}>
                <IconPackage size={15} stroke={1.8} />
                <div className={styles.unitSelect}>
                  <CreatableSelect
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
                    onCreate={handleCreateUnit}
                    searchPlaceholder="Единица…"
                    createLabel={(q) => `Создать «${q}»`}
                    aria-label="Единица измерения"
                  />
                </div>
              </div>
            </div>
            {photoError && <p className={layoutStyles.error}>{photoError}</p>}
          </div>
        </section>

        <section
          className={`${detail.metrics} ${detail.reveal}`}
          style={{ '--reveal-delay': '60ms' } as CSSProperties}
        >
          <label className={detail.metric}>
            <span className={detail.metricIcon}>
              <IconCoin size={18} stroke={1.8} />
            </span>
            <span className={detail.metricBody}>
              <input
                className={styles.metricInput}
                type="text"
                inputMode="decimal"
                value={purchasePrice}
                onChange={(e) => {
                  const normalized = normalizeDecimalInput(e.target.value)
                  if (normalized !== null) setPurchasePrice(normalized)
                }}
                placeholder="0"
              />
              <span>Закупка, ₽</span>
            </span>
          </label>

          <div className={detail.metric}>
            <span className={detail.metricIcon}>
              <IconCheck size={18} stroke={1.8} />
            </span>
            <div className={detail.metricBody}>
              <strong>{liveMargin != null ? `${formatMoney(liveMargin)} ₽` : '—'}</strong>
              <span>Маржа</span>
            </div>
          </div>

          <label className={detail.metric}>
            <span className={detail.metricIcon}>
              <IconAlertTriangle size={18} stroke={1.8} />
            </span>
            <span className={detail.metricBody}>
              <input
                className={styles.metricInput}
                type="text"
                inputMode="decimal"
                value={minStock}
                onChange={(e) => {
                  const normalized = normalizeDecimalInput(e.target.value)
                  if (normalized !== null) setMinStock(normalized)
                }}
                onBlur={() => setMinStock((v) => clampToUnit(v, unitCode))}
                placeholder="0"
              />
              <span>Мин. остаток, {unitLabel}</span>
            </span>
          </label>

          {!product && (
            <label className={detail.metric}>
              <span className={detail.metricIcon}>
                <IconPackage size={18} stroke={1.8} />
              </span>
              <span className={detail.metricBody}>
                <input
                  className={styles.metricInput}
                  type="text"
                  inputMode="decimal"
                  value={initialStockQuantity}
                  onChange={(e) => {
                    const normalized = normalizeDecimalInput(e.target.value)
                    if (normalized !== null) setInitialStockQuantity(normalized)
                  }}
                  onBlur={() => setInitialStockQuantity((v) => clampToUnit(v, unitCode))}
                  placeholder="0"
                />
                <span>Начальный остаток</span>
              </span>
            </label>
          )}
        </section>

        {!product && (
          <section className={`${detail.section} ${detail.reveal}`} style={{ '--reveal-delay': '100ms' } as CSSProperties}>
            <h3 className={detail.sectionTitle}>Склад для начального остатка</h3>
            <div className={styles.sectionControl}>
              <CreatableSelect
                value={initialStockWarehouseId != null ? String(initialStockWarehouseId) : ''}
                onChange={(v) => setInitialStockWarehouseId(v ? Number(v) : null)}
                options={warehouses.map((w) => ({ value: String(w.id), label: w.name }))}
                onCreate={handleCreateWarehouse}
                placeholder="Выберите склад"
                searchPlaceholder="Найти или создать склад…"
                createLabel={(q) => `Создать склад «${q}»`}
              />
            </div>
          </section>
        )}

        <section className={`${detail.section} ${detail.reveal}`} style={{ '--reveal-delay': '130ms' } as CSSProperties}>
          <h3 className={detail.sectionTitle}>Витрина</h3>
          <label className={styles.checkboxRow}>
            <input
              type="checkbox"
              checked={showOnStorefront}
              onChange={(e) => setShowOnStorefront(e.target.checked)}
            />
            Показывать на публичной витрине
          </label>
          {showOnStorefront && (
            <div className={detail.metaGrid}>
              <label className={detail.metaItem}>
                <span className={layoutStyles.textMuted}>Мин. заказ</span>
                <input
                  className={styles.plainInput}
                  type="text"
                  inputMode="decimal"
                  value={storefrontMinQty}
                  onChange={(e) => {
                    const normalized = normalizeDecimalInput(e.target.value)
                    if (normalized !== null) setStorefrontMinQty(normalized)
                  }}
                  placeholder="без ограничения"
                />
              </label>
              <label className={detail.metaItem}>
                <span className={layoutStyles.textMuted}>Шаг заказа</span>
                <input
                  className={styles.plainInput}
                  type="text"
                  inputMode="decimal"
                  value={storefrontStepQty}
                  onChange={(e) => {
                    const normalized = normalizeDecimalInput(e.target.value)
                    if (normalized !== null) setStorefrontStepQty(normalized)
                  }}
                  placeholder="1"
                />
              </label>
            </div>
          )}
        </section>

        <section className={`${detail.section} ${detail.reveal}`} style={{ '--reveal-delay': '160ms' } as CSSProperties}>
          <div className={styles.sectionHead}>
            <h3 className={detail.sectionTitle}>Варианты</h3>
            <Button type="button" variant="secondary" onClick={addVariant}>
              <IconPlus size={14} stroke={1.8} /> Добавить
            </Button>
          </div>
          {variants.length === 0 ? (
            <p className={layoutStyles.textMuted}>Размер / цвет — по желанию</p>
          ) : (
            <div className={styles.variantList}>
              <div className={`${styles.variantRow} ${styles.variantRowHeader}`}>
                <span>Размер</span>
                <span>Цвет</span>
                <span />
              </div>
              {variants.map((v, i) => (
                <div key={i} className={styles.variantRow}>
                  <input value={v.size} onChange={(e) => updateVariant(i, { size: e.target.value })} />
                  <input value={v.color} onChange={(e) => updateVariant(i, { color: e.target.value })} />
                  <IconButton
                    type="button"
                    variant="danger"
                    onClick={() => removeVariant(i)}
                    aria-label="Удалить вариант"
                  >
                    <IconTrash size={16} stroke={1.8} />
                  </IconButton>
                </div>
              ))}
            </div>
          )}
        </section>

        {error && <p className={layoutStyles.error}>{error}</p>}

        <div className={styles.saveBar}>
          <Button type="submit" disabled={saving}>
            {saving ? 'Сохранение…' : submitLabel ?? (product ? 'Сохранить изменения' : 'Создать товар')}
          </Button>
        </div>
      </fieldset>

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
    </form>
  )
}
