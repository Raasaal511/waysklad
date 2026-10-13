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
  setVariantPhoto,
  generateBarcode,
  addStorefrontPhoto,
  setStorefrontPhotos,
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
  IconWand,
} from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { CreatableSelect } from '../../shared/ui/CreatableSelect'
import type { SelectOption } from '../../shared/ui/Select'
import { InfoHint } from '../../shared/ui/InfoHint'
import { isBarcodeScannerSupported } from '../../entities/barcode/barcodeSupport'
import { formatMoney, normalizeDecimalInput } from '../../shared/lib/format'
import { useFeature } from '../../shared/lib/useFeature'
import layoutStyles from '../../shared/ui/Layout.module.css'
import detail from './ProductDetailPage.module.css'
import styles from './ProductForm.module.css'

const BarcodeScanner = lazy(() =>
  import('../../entities/barcode/BarcodeScanner').then((m) => ({ default: m.BarcodeScanner })),
)

const ALLOWED_PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']

const SKU_DIGITS = 13

/**
 * Артикул вида «СКО-1928463750124»: первые 3 буквы названия + 13 случайных цифр.
 * Цифровая часть фиксированной длины и всегда начинается не с нуля — её можно
 * диктовать и искать отдельно от буквенного префикса (поиск товаров ищет
 * подстроку в артикуле, см. product_filter._search_text_expr).
 */
export function generateSku(name: string): string {
  const prefix = name
    .trim()
    .toUpperCase()
    .replace(/[^A-ZА-Я0-9]+/g, '')
    .slice(0, 3)
  // первая цифра 1..9, остальные любые — длина ровно SKU_DIGITS, без ведущего нуля
  let digits = String(1 + Math.floor(Math.random() * 9))
  while (digits.length < SKU_DIGITS) {
    digits += String(Math.floor(Math.random() * 10))
  }
  return prefix ? `${prefix}-${digits}` : digits
}

export function categoryOptions(categories: Category[]): SelectOption[] {
  const result: SelectOption[] = []
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
  const [generatingBarcode, setGeneratingBarcode] = useState(false)
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
    product?.variants.map((v) => ({
      id: v.id,
      size: v.size,
      color: v.color,
      barcode: v.barcode,
      name: v.name,
      // photo обязательно возвращать в PUT: VariantUpdateRequest.photo имеет
      // дефолт "", и без этого поля сохранение товара стёрло бы уже
      // загруженное фото варианта
      photo: v.photo,
    })) ?? [],
  )
  // выбранные, но ещё не отправленные файлы фото вариантов: ключ — индекс в
  // variants. Грузятся после сохранения товара, когда у варианта есть id
  const [variantPhotoFiles, setVariantPhotoFiles] = useState<Record<number, File>>({})
  const [variantPhotoPreviews, setVariantPhotoPreviews] = useState<Record<number, string>>({})
  const [initialStockWarehouseId, setInitialStockWarehouseId] = useState<number | null>(
    warehouses[0]?.id ?? null,
  )
  const [initialStockQuantity, setInitialStockQuantity] = useState('')
  const storefrontEnabled = useFeature('storefront')
  const [showOnStorefront, setShowOnStorefront] = useState(product?.show_on_storefront ?? false)
  const [storefrontMinQty, setStorefrontMinQty] = useState(product?.storefront_min_qty ?? '')
  const [storefrontStepQty, setStorefrontStepQty] = useState(product?.storefront_step_qty ?? '')
  const [description, setDescription] = useState(product?.description ?? '')
  const [warrantyText, setWarrantyText] = useState(product?.warranty_text ?? '')
  const [storefrontPhotos, setStorefrontPhotosState] = useState<string[]>(
    product?.storefront_photos ?? [],
  )
  const [galleryBusy, setGalleryBusy] = useState(false)
  const [galleryDragActive, setGalleryDragActive] = useState(false)
  const [dragPhotoIndex, setDragPhotoIndex] = useState<number | null>(null)
  const galleryInputRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const savedProductId = product?.id ?? createdProduct?.id

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

  async function handleGenerateBarcode() {
    setGeneratingBarcode(true)
    setError(null)
    try {
      const { barcode: next } = await generateBarcode()
      setBarcode(next)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сгенерировать штрихкод')
    } finally {
      setGeneratingBarcode(false)
    }
  }

  async function handleAddGalleryFiles(files: FileList | null) {
    if (!files?.length) return
    const productId = await ensureDraftProduct()
    if (!productId) {
      if (galleryInputRef.current) galleryInputRef.current.value = ''
      return
    }
    setGalleryBusy(true)
    setError(null)
    try {
      let next = storefrontPhotos
      for (const file of Array.from(files)) {
        if (!ALLOWED_PHOTO_TYPES.includes(file.type)) {
          setError('Неподдерживаемый формат. JPG, PNG, WEBP или GIF.')
          continue
        }
        const updated = await addStorefrontPhoto(productId, file)
        next = updated.storefront_photos ?? []
        setStorefrontPhotosState(next)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить фото витрины')
    } finally {
      setGalleryBusy(false)
      if (galleryInputRef.current) galleryInputRef.current.value = ''
    }
  }

  async function persistGallery(photos: string[]) {
    if (!savedProductId) return
    setGalleryBusy(true)
    setError(null)
    try {
      const updated = await setStorefrontPhotos(savedProductId, photos)
      setStorefrontPhotosState(updated.storefront_photos ?? photos)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось обновить галерею')
    } finally {
      setGalleryBusy(false)
    }
  }

  async function removeGalleryPhoto(url: string) {
    await persistGallery(storefrontPhotos.filter((p) => p !== url))
  }

  function onGalleryDragStart(index: number) {
    setDragPhotoIndex(index)
  }

  async function onGalleryDrop(index: number) {
    if (dragPhotoIndex == null || dragPhotoIndex === index) {
      setDragPhotoIndex(null)
      return
    }
    const next = [...storefrontPhotos]
    const [moved] = next.splice(dragPhotoIndex, 1)
    next.splice(index, 0, moved)
    setDragPhotoIndex(null)
    setStorefrontPhotosState(next)
    await persistGallery(next)
  }

  function addVariant() {
    setVariants((v) => [...v, { size: '', color: '', name: '' }])
  }

  function updateVariant(index: number, patch: Partial<VariantInput>) {
    setVariants((v) => v.map((item, i) => (i === index ? { ...item, ...patch } : item)))
  }

  function removeVariant(index: number) {
    setVariants((v) => v.filter((_, i) => i !== index))
    // ключи в variantPhotoFiles — индексы в variants, поэтому после удаления
    // строки все последующие сдвигаются на единицу: без пересборки файл
    // достался бы соседнему варианту
    const shiftKeys = <T,>(map: Record<number, T>): Record<number, T> =>
      Object.fromEntries(
        Object.entries(map)
          .map(([key, value]) => [Number(key), value] as const)
          .filter(([key]) => key !== index)
          .map(([key, value]) => [key > index ? key - 1 : key, value]),
      )
    setVariantPhotoFiles(shiftKeys)
    setVariantPhotoPreviews(shiftKeys)
  }

  function applyVariantPhotoFile(index: number, file: File | null) {
    if (!file) return
    if (!ALLOWED_PHOTO_TYPES.includes(file.type)) {
      setError('Неподдерживаемый формат файла. Загрузите изображение JPG, PNG, WEBP или GIF.')
      return
    }
    setError(null)
    setVariantPhotoFiles((prev) => ({ ...prev, [index]: file }))
    setVariantPhotoPreviews((prev) => ({ ...prev, [index]: URL.createObjectURL(file) }))
  }

  function removeVariantPhoto(index: number) {
    setVariantPhotoFiles((prev) => {
      const next = { ...prev }
      delete next[index]
      return next
    })
    setVariantPhotoPreviews((prev) => {
      const next = { ...prev }
      delete next[index]
      return next
    })
    // пустая строка в photo — сигнал бэкенду убрать уже сохранённое фото
    updateVariant(index, { photo: '' })
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

  async function persistProduct(): Promise<Product> {
    const payload = {
      name,
      sku,
      barcode: barcode || null,
      unit_code: unitCode,
      purchase_price: purchasePrice || '0',
      retail_price: retailPrice || '0',
      min_stock: minStock || '0',
      category_id: categoryId,
      description,
      warranty_text: warrantyText,
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
    // фото вариантов — только после сохранения товара: до него у новых
    // вариантов нет id. Порядок saved.variants совпадает с порядком
    // отправленного списка (бэкенд пересобирает варианты из него)
    const pendingVariantPhotos = Object.entries(variantPhotoFiles)
    if (pendingVariantPhotos.length > 0) {
      for (const [key, file] of pendingVariantPhotos) {
        const variant = saved.variants[Number(key)]
        if (!variant) continue
        saved = await setVariantPhoto(saved.id, variant.id, file)
      }
      setVariantPhotoFiles({})
      setVariantPhotoPreviews({})
      setVariants(
        saved.variants.map((v) => ({
          id: v.id,
          size: v.size,
          color: v.color,
          barcode: v.barcode,
          name: v.name,
          photo: v.photo,
        })),
      )
    }
    return saved
  }

  // Черновик товара нужен для фото витрины — оно грузится отдельным запросом
  // по product_id, которого нет до первого сохранения. Название обязательно
  // и на бэкенде, и в форме (required) — без него сохранить нечего.
  async function ensureDraftProduct(): Promise<number | null> {
    if (savedProductId) return savedProductId
    if (!name.trim()) {
      setError('Сначала укажите название товара — тогда можно будет добавить фото витрины')
      return null
    }
    setSaving(true)
    onSavingChange?.(true)
    setError(null)
    try {
      const saved = await persistProduct()
      return saved.id
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить товар')
      return null
    } finally {
      setSaving(false)
      onSavingChange?.(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    onSavingChange?.(true)
    try {
      const saved = await persistProduct()
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
                    <IconX size={18} stroke={2.4} />
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
                  {storefrontEnabled && showOnStorefront && (
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
                <IconButton
                  type="button"
                  variant="muted"
                  onClick={handleGenerateBarcode}
                  disabled={generatingBarcode}
                  aria-label="Сгенерировать штрихкод"
                  tooltip="Сгенерировать"
                >
                  <IconWand size={15} stroke={1.8} />
                </IconButton>
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
            <span className={`${detail.metricIcon} ${detail.metricIconWarn}`}>
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
                aria-describedby="min-stock-hint"
              />
              <span className={styles.metricLabelWithHint}>
                Порог предупреждения
                <InfoHint text={`Когда остаток станет меньше этого значения, товар подсветится как заканчивающийся. Единица: ${unitLabel}.`} />
              </span>
              <span id="min-stock-hint" className={styles.metricHint}>
                Ниже этого числа — предупреждение о низком остатке
              </span>
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

        {storefrontEnabled && (
        <section className={`${styles.showcaseCard} ${detail.reveal}`} style={{ '--reveal-delay': '110ms' } as CSSProperties}>
          <div className={styles.showcaseHead}>
            <h3 className={detail.sectionTitle}>Витрина</h3>
            <p className={styles.showcaseSubtitle}>Как товар увидит покупатель в магазине</p>
          </div>

          <div className={styles.showcaseBody}>
            <label className={styles.showcaseField}>
              <span className={styles.showcaseFieldLabel}>Описание</span>
              <textarea
                className={styles.descriptionInput}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                maxLength={4000}
                placeholder="Расскажите о товаре — это увидят покупатели на витрине"
              />
            </label>

            <label className={styles.showcaseField}>
              <span className={styles.showcaseFieldLabel}>Гарантия</span>
              <textarea
                className={styles.descriptionInput}
                value={warrantyText}
                onChange={(e) => setWarrantyText(e.target.value)}
                rows={3}
                maxLength={5000}
                placeholder="Условия гарантии — покажем отдельным блоком на карточке товара"
              />
            </label>

            <div className={styles.showcaseField}>
              <div className={styles.showcaseFieldLabelRow}>
                <span className={styles.showcaseFieldLabel}>
                  Фото витрины
                  {storefrontPhotos.length > 0 && (
                    <span className={styles.galleryCount}>{storefrontPhotos.length}</span>
                  )}
                </span>
              </div>

              {!savedProductId && (
                <p className={styles.fieldHint}>
                  {name.trim()
                    ? 'Товар сохранится автоматически при добавлении первого фото'
                    : 'Укажите название товара выше — тогда можно будет добавить фото'}
                </p>
              )}

              <div
                className={[styles.galleryGrid, galleryDragActive ? styles.galleryGridActive : '']
                  .filter(Boolean)
                  .join(' ')}
                onDragOver={(e) => {
                  e.preventDefault()
                  setGalleryDragActive(true)
                }}
                onDragLeave={() => setGalleryDragActive(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setGalleryDragActive(false)
                  if (e.dataTransfer.files?.length) handleAddGalleryFiles(e.dataTransfer.files)
                }}
              >
                {storefrontPhotos.map((url, index) => (
                  <div
                    key={url}
                    className={styles.galleryItem}
                    draggable={!galleryBusy}
                    onDragStart={() => onGalleryDragStart(index)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={() => onGalleryDrop(index)}
                  >
                    <img src={url} alt="" />
                    <div className={styles.galleryItemOverlay}>
                      <button
                        type="button"
                        className={styles.galleryRemove}
                        onClick={() => removeGalleryPhoto(url)}
                        disabled={galleryBusy}
                        aria-label="Удалить фото"
                      >
                        <IconX size={14} stroke={2.2} />
                      </button>
                    </div>
                    {index === 0 && <span className={styles.galleryMainBadge}>Главное</span>}
                  </div>
                ))}
                <button
                  type="button"
                  className={styles.galleryAddTile}
                  onClick={() => galleryInputRef.current?.click()}
                  disabled={galleryBusy || saving}
                >
                  <IconPhoto size={20} stroke={1.6} />
                  <span>Добавить</span>
                </button>
                <input
                  ref={galleryInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  multiple
                  hidden
                  onChange={(e) => handleAddGalleryFiles(e.target.files)}
                />
              </div>
              {storefrontPhotos.length > 1 && (
                <p className={styles.fieldHint}>Перетащите миниатюры, чтобы изменить порядок</p>
              )}
            </div>

            <label className={styles.showcaseToggle}>
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
                  <span className={styles.fieldLabelWithHint}>
                    <span className={layoutStyles.textMuted}>Минимум для покупки</span>
                    <InfoHint text="Покупатель на витрине не сможет заказать меньше этого количества. Например, минимум 2 — нельзя взять 1 штуку." />
                  </span>
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
                  <span className={styles.fieldHint}>Сколько минимум можно взять в одном заказе</span>
                </label>
                <label className={detail.metaItem}>
                  <span className={styles.fieldLabelWithHint}>
                    <span className={layoutStyles.textMuted}>Прибавка кнопками + / −</span>
                    <InfoHint text="На сколько меняется количество, когда покупатель нажимает + или − на витрине. Например, 0.5 — можно выбрать 0.5, 1, 1.5…" />
                  </span>
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
                  <span className={styles.fieldHint}>Шаг изменения количества на витрине</span>
                </label>
              </div>
            )}
          </div>
        </section>
        )}

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
                <span>Фото</span>
                <span>Название</span>
                <span>Размер</span>
                <span>Цвет</span>
                <span />
              </div>
              {variants.map((v, i) => {
                const preview = variantPhotoPreviews[i] ?? v.photo ?? ''
                return (
                <div key={i} className={styles.variantRow}>
                  <div className={styles.variantPhoto}>
                    <label className={styles.variantPhotoPick}>
                      <input
                        type="file"
                        accept={ALLOWED_PHOTO_TYPES.join(',')}
                        className={styles.variantPhotoInput}
                        onChange={(e) => applyVariantPhotoFile(i, e.target.files?.[0] ?? null)}
                      />
                      {preview ? (
                        <img src={preview} alt="" className={styles.variantPhotoImg} />
                      ) : (
                        <span className={styles.variantPhotoEmpty} aria-hidden="true">
                          <IconPhoto size={16} stroke={1.8} />
                        </span>
                      )}
                      <span className="sr-only">
                        {preview ? 'Заменить фото варианта' : 'Добавить фото варианта'}
                      </span>
                    </label>
                    {preview && (
                      <button
                        type="button"
                        className={styles.variantPhotoRemove}
                        onClick={() => removeVariantPhoto(i)}
                        aria-label="Убрать фото варианта"
                      >
                        <IconX size={11} stroke={2.4} />
                      </button>
                    )}
                  </div>
                  <input
                    value={v.name ?? ''}
                    onChange={(e) => updateVariant(i, { name: e.target.value })}
                    placeholder="например, Aurum. Если пусто — цвет · размер"
                  />
                  <input value={v.size} onChange={(e) => updateVariant(i, { size: e.target.value })} placeholder="Размер" />
                  <input value={v.color} onChange={(e) => updateVariant(i, { color: e.target.value })} placeholder="Цвет" />
                  <IconButton
                    type="button"
                    variant="danger"
                    onClick={() => removeVariant(i)}
                    aria-label="Удалить вариант"
                  >
                    <IconTrash size={16} stroke={1.8} />
                  </IconButton>
                </div>
                )
              })}
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
