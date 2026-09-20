import { useEffect, useState } from 'react'
import { IconAdjustments } from '@tabler/icons-react'
import { plural } from '../../../shared/lib/format'
import { Button } from '../../../shared/ui/Button'
import { Chip, RemovableChip } from '../../../shared/ui/Chip'
import { Modal } from '../../../shared/ui/Modal'
import { Select, type SelectOption } from '../../../shared/ui/Select'
import styles from './FilterBar.module.css'

export interface FilterBarValue {
  minPrice: string
  maxPrice: string
  inStockOnly: boolean
  variantSize: string
  variantColor: string
  minRating: number | null
  /** Только маркетплейс: «Со скидкой» (M-F4 §1). */
  withDiscount?: boolean
  /** Только маркетплейс: город магазина, синхронизирован с шапкой (M-F4 §1). */
  city?: string
}

const EMPTY_FILTERS: FilterBarValue = {
  minPrice: '',
  maxPrice: '',
  inStockOnly: false,
  variantSize: '',
  variantColor: '',
  minRating: null,
  withDiscount: false,
  city: '',
}

export interface FilterBarCategory {
  /** number — id категории магазина (каталог); string — slug платформенной категории (маркетплейс). */
  id: number | string
  name: string
  count: number
}

interface FilterBarProps {
  sort: string
  sortOptions: SelectOption[]
  onSortChange: (value: string) => void
  value: FilterBarValue
  /** Применяет частичное изменение сразу (значения живут в URL у вызывающей страницы). */
  onChange: (patch: Partial<FilterBarValue>) => void
  onClear: () => void
  availableSizes?: string[]
  availableColors?: string[]
  /** Категории платформы/магазина лентой чипов; скрыта при пустом списке. */
  categories?: FilterBarCategory[]
  /** Список категорий ещё грузится — рисуем skeleton-ленту той же высоты вместо
   *  того, чтобы дождаться загрузки и раздвинуть макет (нулевой CLS, блок «Д» п.9). */
  categoriesLoading?: boolean
  activeCategoryId?: number | string | null
  onCategoryChange?: (id: number | string | null) => void
  totalCount?: number
  resultCount: number
  /** Только маркетплейс: список городов для селекта «Город» — скрыт, если не передан. */
  cityOptions?: SelectOption[]
}

const RATING_OPTIONS = [5, 4, 3] as const

function countActive(v: FilterBarValue): number {
  let n = 0
  if (v.minPrice) n++
  if (v.maxPrice) n++
  if (v.inStockOnly) n++
  if (v.variantSize) n++
  if (v.variantColor) n++
  if (v.minRating) n++
  if (v.withDiscount) n++
  if (v.city) n++
  return n
}

/** Общая панель фильтров — каталог магазина и (позже) маркетплейс. Блок «Д» шаг P3 п.2. */
export function FilterBar({
  sort,
  sortOptions,
  onSortChange,
  value,
  onChange,
  onClear,
  availableSizes = [],
  availableColors = [],
  categories = [],
  categoriesLoading = false,
  activeCategoryId = null,
  onCategoryChange,
  totalCount,
  resultCount,
  cityOptions,
}: FilterBarProps) {
  const [sheetOpen, setSheetOpen] = useState(false)
  // черновик цены — применяется по blur/Enter, чтобы не бить URL/каталог на каждый символ
  const [minPriceDraft, setMinPriceDraft] = useState(value.minPrice)
  const [maxPriceDraft, setMaxPriceDraft] = useState(value.maxPrice)
  // черновик внутри шита — отдельная копия, применяется целиком по «Показать N товаров»
  const [sheetDraft, setSheetDraft] = useState(value)

  useEffect(() => {
    setMinPriceDraft(value.minPrice)
    setMaxPriceDraft(value.maxPrice)
  }, [value.minPrice, value.maxPrice])

  useEffect(() => {
    if (sheetOpen) setSheetDraft(value)
  }, [sheetOpen, value])

  const activeCount = countActive(value)
  const hasSizeColor = availableSizes.length > 0 || availableColors.length > 0

  const activeChips: { key: string; label: string; clear: Partial<FilterBarValue> }[] = []
  if (value.minPrice) activeChips.push({ key: 'min', label: `от ${value.minPrice} ₽`, clear: { minPrice: '' } })
  if (value.maxPrice) activeChips.push({ key: 'max', label: `до ${value.maxPrice} ₽`, clear: { maxPrice: '' } })
  if (value.inStockOnly) activeChips.push({ key: 'stock', label: 'В наличии', clear: { inStockOnly: false } })
  if (value.variantSize) activeChips.push({ key: 'size', label: `Размер ${value.variantSize}`, clear: { variantSize: '' } })
  if (value.variantColor) activeChips.push({ key: 'color', label: value.variantColor, clear: { variantColor: '' } })
  if (value.minRating) activeChips.push({ key: 'rating', label: `от ${value.minRating}★`, clear: { minRating: null } })
  if (value.withDiscount) activeChips.push({ key: 'discount', label: 'Со скидкой', clear: { withDiscount: false } })
  if (value.city) {
    const cityLabel = cityOptions?.find((o) => o.value === value.city)?.label ?? value.city
    activeChips.push({ key: 'city', label: cityLabel, clear: { city: '' } })
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.toolbar}>
        <Select value={sort} onChange={onSortChange} options={sortOptions} aria-label="Сортировка" />
        <Button
          variant="secondary"
          active={activeCount > 0}
          className={styles.filtersToggle}
          onClick={() => setSheetOpen(true)}
        >
          <IconAdjustments size={18} stroke={1.8} />
          Фильтры{activeCount > 0 ? ` (${activeCount})` : ''}
        </Button>

        {/* ≥1024 — поля раскрыты в строке (п.2), скрыты в DOM на <1024 через CSS,
            чтобы не дублировать разметку между строкой и нижним шитом. */}
        <div className={styles.inline}>
          <input
            type="text"
            inputMode="decimal"
            className={styles.priceInput}
            value={minPriceDraft}
            onChange={(e) => setMinPriceDraft(e.target.value)}
            onBlur={() => onChange({ minPrice: minPriceDraft.trim() })}
            placeholder="Цена от"
            aria-label="Цена от"
          />
          <input
            type="text"
            inputMode="decimal"
            className={styles.priceInput}
            value={maxPriceDraft}
            onChange={(e) => setMaxPriceDraft(e.target.value)}
            onBlur={() => onChange({ maxPrice: maxPriceDraft.trim() })}
            placeholder="до"
            aria-label="Цена до"
          />
          <label className={styles.toggleField}>
            <input
              type="checkbox"
              checked={value.inStockOnly}
              onChange={(e) => onChange({ inStockOnly: e.target.checked })}
            />
            Только в наличии
          </label>
          {availableSizes.map((s) => (
            <Chip key={s} active={value.variantSize === s} onClick={() => onChange({ variantSize: value.variantSize === s ? '' : s })}>
              {s}
            </Chip>
          ))}
          {availableColors.map((c) => (
            <Chip key={c} active={value.variantColor === c} onClick={() => onChange({ variantColor: value.variantColor === c ? '' : c })}>
              {c}
            </Chip>
          ))}
          <Chip active={!!value.minRating} onClick={() => onChange({ minRating: value.minRating ? null : 4 })}>
            от 4★
          </Chip>
          {cityOptions && (
            <Chip active={!!value.withDiscount} onClick={() => onChange({ withDiscount: !value.withDiscount })}>
              Со скидкой
            </Chip>
          )}
          {cityOptions && (
            <Select
              value={value.city ?? ''}
              onChange={(v) => onChange({ city: v })}
              options={[{ value: '', label: 'Все города' }, ...cityOptions]}
              aria-label="Город"
            />
          )}
        </div>
      </div>

      {activeChips.length > 0 && (
        <div className={styles.activeRow}>
          {activeChips.map((c) => (
            <RemovableChip key={c.key} onRemove={() => onChange(c.clear)} removeLabel={`Убрать фильтр «${c.label}»`}>
              {c.label}
            </RemovableChip>
          ))}
          <button type="button" className={styles.clearAll} onClick={onClear}>
            Сбросить всё
          </button>
        </div>
      )}

      {categoriesLoading ? (
        <div className={styles.categories} aria-hidden="true">
          {[64, 88, 72, 96].map((w, i) => (
            <span key={i} className={styles.categorySkeleton} style={{ width: w }} />
          ))}
        </div>
      ) : (
        categories.length > 0 && (
          <div className={styles.categories}>
            <Chip active={activeCategoryId == null} onClick={() => onCategoryChange?.(null)}>
              Все{totalCount != null ? ` ${totalCount}` : ''}
            </Chip>
            {categories.map((c) => (
              <Chip key={c.id} active={activeCategoryId === c.id} onClick={() => onCategoryChange?.(c.id)}>
                {c.name} {c.count}
              </Chip>
            ))}
          </div>
        )
      )}

      {sheetOpen && (
        <Modal
          title="Фильтры"
          onClose={() => setSheetOpen(false)}
          footer={
            <>
              <Button
                variant="secondary"
                onClick={() => {
                  setSheetDraft(EMPTY_FILTERS)
                  setMinPriceDraft('')
                  setMaxPriceDraft('')
                }}
              >
                Сбросить
              </Button>
              <Button
                onClick={() => {
                  onChange(sheetDraft)
                  setMinPriceDraft(sheetDraft.minPrice)
                  setMaxPriceDraft(sheetDraft.maxPrice)
                  setSheetOpen(false)
                }}
              >
                Показать {resultCount} {plural(resultCount, ['товар', 'товара', 'товаров'])}
              </Button>
            </>
          }
        >
          <div className={styles.sheetBody}>
            <div className={styles.sheetPriceRow}>
              <label className={styles.sheetField}>
                Цена от
                <input
                  type="text"
                  inputMode="decimal"
                  value={sheetDraft.minPrice}
                  onChange={(e) => setSheetDraft((d) => ({ ...d, minPrice: e.target.value }))}
                  placeholder="0"
                />
              </label>
              <label className={styles.sheetField}>
                до
                <input
                  type="text"
                  inputMode="decimal"
                  value={sheetDraft.maxPrice}
                  onChange={(e) => setSheetDraft((d) => ({ ...d, maxPrice: e.target.value }))}
                  placeholder="∞"
                />
              </label>
            </div>

            <label className={styles.toggleField}>
              <input
                type="checkbox"
                checked={sheetDraft.inStockOnly}
                onChange={(e) => setSheetDraft((d) => ({ ...d, inStockOnly: e.target.checked }))}
              />
              Только в наличии
            </label>

            {hasSizeColor && (
              <div className={styles.sheetChipGroup}>
                {availableSizes.map((s) => (
                  <Chip
                    key={s}
                    active={sheetDraft.variantSize === s}
                    onClick={() => setSheetDraft((d) => ({ ...d, variantSize: d.variantSize === s ? '' : s }))}
                  >
                    {s}
                  </Chip>
                ))}
                {availableColors.map((c) => (
                  <Chip
                    key={c}
                    active={sheetDraft.variantColor === c}
                    onClick={() => setSheetDraft((d) => ({ ...d, variantColor: d.variantColor === c ? '' : c }))}
                  >
                    {c}
                  </Chip>
                ))}
              </div>
            )}

            <div className={styles.sheetChipGroup}>
              {RATING_OPTIONS.map((r) => (
                <Chip
                  key={r}
                  active={sheetDraft.minRating === r}
                  onClick={() => setSheetDraft((d) => ({ ...d, minRating: d.minRating === r ? null : r }))}
                >
                  от {r}★
                </Chip>
              ))}
            </div>

            {cityOptions && (
              <>
                <Chip
                  active={!!sheetDraft.withDiscount}
                  onClick={() => setSheetDraft((d) => ({ ...d, withDiscount: !d.withDiscount }))}
                >
                  Со скидкой
                </Chip>
                <label className={styles.sheetField}>
                  Город
                  <Select
                    value={sheetDraft.city ?? ''}
                    onChange={(v) => setSheetDraft((d) => ({ ...d, city: v }))}
                    options={[{ value: '', label: 'Все города' }, ...cityOptions]}
                    aria-label="Город"
                  />
                </label>
              </>
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}
