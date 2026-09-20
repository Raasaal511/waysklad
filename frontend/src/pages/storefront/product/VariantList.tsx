import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { IconMinus, IconPlus, IconSearch, IconInfoCircle, IconArrowsMaximize } from '@tabler/icons-react'
import type { StorefrontProductDetail, StorefrontVariant } from '../../../entities/storefront/api'
import { initialOrderQty, bumpOrderQty } from '../../../entities/storefront/api'
import { formatMoney, formatQuantity } from '../../../shared/lib/format'
import { Lightbox } from '../../../shared/ui/Lightbox'
import { stockText, variantPrice } from './productUtils'
import type { SelectionKey } from './useSelection'
import styles from './VariantList.module.css'

const SEARCH_THRESHOLD = 6
const COLLAPSE_THRESHOLD = 8

interface VariantRow {
  key: SelectionKey
  variant: StorefrontVariant | null
  displayName: string
  photo: string
}

interface VariantListProps {
  product: StorefrontProductDetail
  selection: Map<SelectionKey, number>
  onQtyChange: (key: SelectionKey, qty: number) => void
  onShowToast: (message: string) => void
  /** Ключ строки, которую нужно однократно подсветить пульсацией — например,
   * после того как «В корзину» сама выбрала вариант за покупателя (п.6 промпта P4). */
  flashKey?: SelectionKey | null
}

export function VariantList({ product, selection, onQtyChange, onShowToast, flashKey }: VariantListProps) {
  const [searchParams] = useSearchParams()
  const highlightId = searchParams.get('v')
  const [query, setQuery] = useState('')
  const [colorFilter, setColorFilter] = useState<string | null>(null)
  const [sizeFilter, setSizeFilter] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)
  const [lightboxRow, setLightboxRow] = useState<number | null>(null)
  const rowRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const scrolledToHighlight = useRef(false)

  // товар без вариантов (или с единственным вариантом) показывает не строку выбора,
  // а отдельный блок «Количество» — см. renderQuantityBlock ниже
  const isSingleItem = product.variants.length <= 1
  const singleVariant = product.variants.length === 1 ? product.variants[0] : null

  const rows: VariantRow[] = useMemo(() => {
    if (product.variants.length === 0) {
      return [{ key: 'base', variant: null, displayName: product.name, photo: product.photo }]
    }
    return product.variants.map((v) => ({
      key: v.id,
      variant: v,
      displayName: v.display_name,
      photo: v.photo || product.photo,
    }))
  }, [product])

  const singleRow = rows[0]

  const uniqueColors = useMemo(
    () => Array.from(new Set(product.variants.map((v) => v.color).filter(Boolean))),
    [product.variants],
  )
  const uniqueSizes = useMemo(
    () => Array.from(new Set(product.variants.map((v) => v.size).filter(Boolean))),
    [product.variants],
  )

  const showTools = product.variants.length > SEARCH_THRESHOLD

  const filteredRows = useMemo(() => {
    let list = rows
    if (showTools && query.trim()) {
      const q = query.trim().toLowerCase()
      list = list.filter((r) => r.displayName.toLowerCase().includes(q))
    }
    if (showTools && colorFilter) {
      list = list.filter((r) => r.variant?.color === colorFilter)
    }
    if (showTools && sizeFilter) {
      list = list.filter((r) => r.variant?.size === sizeFilter)
    }
    return list
  }, [rows, query, colorFilter, sizeFilter, showTools])

  const visibleRows =
    !showAll && filteredRows.length > COLLAPSE_THRESHOLD ? filteredRows.slice(0, COLLAPSE_THRESHOLD) : filteredRows

  useEffect(() => {
    if (!highlightId || scrolledToHighlight.current) return
    const el = rowRefs.current.get(highlightId)
    if (el) {
      scrolledToHighlight.current = true
      // если подсвеченный вариант скрыт коллапсом — раскрыть список
      setShowAll(true)
      requestAnimationFrame(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }))
    }
  }, [highlightId, filteredRows])

  useEffect(() => {
    if (flashKey == null) return
    const el = rowRefs.current.get(String(flashKey))
    if (el) {
      setShowAll(true)
      requestAnimationFrame(() => el.scrollIntoView({ behavior: 'smooth', block: 'center' }))
    }
  }, [flashKey])

  function handleStep(row: VariantRow, deltaSteps: number) {
    const current = selection.get(row.key) ?? 0
    const min = row.variant?.stock_qty != null ? Number(row.variant.stock_qty) : 9999
    if (current === 0 && deltaSteps > 0) {
      const start = initialOrderQty(product.min_order_qty, product.order_step_qty)
      if (start > min) {
        onShowToast('Больше нет в наличии')
        return
      }
      onQtyChange(row.key, start)
      return
    }
    const next = bumpOrderQty(current, deltaSteps, product.min_order_qty, product.order_step_qty)
    if (deltaSteps > 0 && next > min) {
      onShowToast('Больше нет в наличии')
      return
    }
    onQtyChange(row.key, next)
  }

  function handleDirectInput(row: VariantRow, raw: string) {
    const digits = raw.replace(/\D/g, '')
    if (digits === '') {
      onQtyChange(row.key, 0)
      return
    }
    const min = row.variant?.stock_qty != null ? Number(row.variant.stock_qty) : 9999
    const value = Math.min(Number(digits), 9999)
    if (value > min) {
      onShowToast('Больше нет в наличии')
      onQtyChange(row.key, min)
      return
    }
    onQtyChange(row.key, value)
  }

  const qtyHintParts: string[] = []
  if (product.min_order_qty)
    qtyHintParts.push(`мин. ${formatQuantity(product.min_order_qty)} ${product.unit_label}`)
  if (product.order_step_qty) qtyHintParts.push(`шаг ${formatQuantity(product.order_step_qty)}`)

  const lightboxPhotos = rows.map((r) => r.photo).filter(Boolean)

  // товар без вариантов (или с одним) — не список строк, а один блок «Количество»
  // со степпером и ценой за единицу (п.5 промпта P4)
  if (isSingleItem) {
    const qty = selection.get(singleRow.key) ?? 0
    const isSelected = qty > 0
    const inStock = singleVariant ? singleVariant.in_stock : product.in_stock
    const unitPrice = singleVariant ? variantPrice(product, singleVariant) : product.retail_price
    const stockObj = singleVariant
      ? { in_stock: singleVariant.in_stock, stock_level: singleVariant.stock_level, stock_qty: singleVariant.stock_qty }
      : { in_stock: product.in_stock, stock_level: product.stock_level, stock_qty: product.stock_qty }
    const stockLabel = stockText(stockObj, product.unit_label)
    const highlighted = (highlightId != null && String(singleRow.key) === highlightId) || flashKey === singleRow.key

    return (
      <div className={styles.wrap}>
        <div
          className={[styles.qtyBlock, highlighted ? styles.rowHighlight : ''].filter(Boolean).join(' ')}
          ref={(el) => {
            if (el) rowRefs.current.set(String(singleRow.key), el)
            else rowRefs.current.delete(String(singleRow.key))
          }}
        >
          <div className={styles.qtyBlockInfo}>
            <p className={styles.qtyBlockPrice}>
              {formatMoney(unitPrice)} ₽ <span className={styles.qtyBlockUnit}>за {product.unit_label || 'шт'}</span>
            </p>
            <p
              className={[
                styles.rowStock,
                stockObj.stock_level === 'low' ? styles.rowStockLow : '',
                !inStock ? styles.rowStockOut : '',
              ]
                .filter(Boolean)
                .join(' ')}
            >
              {stockLabel}
            </p>
          </div>

          {inStock && (
            <div className={styles.stepper}>
              <button
                type="button"
                className={`${styles.stepBtn} ${styles.stepMinus}`}
                onClick={() => handleStep(singleRow, -1)}
                aria-label="Уменьшить количество"
                disabled={!isSelected}
              >
                <IconMinus size={16} stroke={2} />
              </button>
              <input
                className={styles.stepValue}
                type="text"
                inputMode="numeric"
                value={String(qty)}
                onChange={(e) => handleDirectInput(singleRow, e.target.value)}
                aria-label="Количество"
              />
              <button
                type="button"
                className={`${styles.stepBtn} ${styles.stepPlus}`}
                onClick={() => handleStep(singleRow, 1)}
                aria-label="Увеличить количество"
              >
                <IconPlus size={16} stroke={2} />
              </button>
            </div>
          )}
        </div>

        {qtyHintParts.length > 0 && (
          <p className={styles.hint}>
            <IconInfoCircle size={14} stroke={1.8} />
            {qtyHintParts.join(' · ')}
          </p>
        )}
      </div>
    )
  }

  return (
    <div className={styles.wrap}>
      {showTools && (
        <div className={styles.toolsRow}>
          <label className={styles.searchField}>
            <IconSearch size={15} stroke={1.8} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Найти вариант…"
              aria-label="Поиск по вариантам"
            />
          </label>
          {uniqueColors.map((c) => (
            <button
              key={c}
              type="button"
              className={colorFilter === c ? `${styles.filterChip} ${styles.filterChipActive}` : styles.filterChip}
              onClick={() => setColorFilter((prev) => (prev === c ? null : c))}
            >
              {c}
            </button>
          ))}
          {uniqueSizes.map((s) => (
            <button
              key={s}
              type="button"
              className={sizeFilter === s ? `${styles.filterChip} ${styles.filterChipActive}` : styles.filterChip}
              onClick={() => setSizeFilter((prev) => (prev === s ? null : s))}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {visibleRows.map((row) => {
        const qty = selection.get(row.key) ?? 0
        const isSelected = qty > 0
        const inStock = row.variant ? row.variant.in_stock : product.in_stock
        const rowPrice = row.variant ? variantPrice(product, row.variant) : product.retail_price
        const priceDiffers = row.variant?.price != null && row.variant.price !== product.retail_price
        const rowIndexForLightbox = lightboxPhotos.indexOf(row.photo)
        const highlighted = (highlightId != null && String(row.key) === highlightId) || flashKey === row.key

        const stockObj = row.variant
          ? { in_stock: row.variant.in_stock, stock_level: row.variant.stock_level, stock_qty: row.variant.stock_qty }
          : { in_stock: product.in_stock, stock_level: product.stock_level, stock_qty: product.stock_qty }
        const stockLabel = stockText(stockObj, product.unit_label)

        return (
          <div
            key={String(row.key)}
            ref={(el) => {
              if (el) rowRefs.current.set(String(row.key), el)
              else rowRefs.current.delete(String(row.key))
            }}
            className={[
              styles.row,
              isSelected ? styles.rowSelected : '',
              !inStock ? styles.rowMuted : '',
              highlighted ? styles.rowHighlight : '',
            ]
              .filter(Boolean)
              .join(' ')}
          >
            {row.photo ? (
              <button
                type="button"
                className={styles.rowThumbWrap}
                onClick={() => rowIndexForLightbox >= 0 && setLightboxRow(rowIndexForLightbox)}
                aria-label="Открыть фото"
              >
                <img src={row.photo} alt="" />
                <span className={styles.rowThumbExpand}>
                  <IconArrowsMaximize size={10} stroke={2} />
                </span>
              </button>
            ) : (
              <div className={styles.rowThumbWrap} />
            )}

            <div className={styles.rowBody}>
              <p className={styles.rowName}>{row.displayName}</p>
              <p
                className={[
                  styles.rowStock,
                  stockObj.stock_level === 'low' ? styles.rowStockLow : '',
                  !inStock ? styles.rowStockOut : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                {stockLabel}
              </p>
              {priceDiffers && <p className={styles.rowPrice}>{formatMoney(rowPrice)} ₽</p>}
            </div>

            {!inStock ? null : isSelected ? (
              <div className={styles.stepper}>
                <button
                  type="button"
                  className={`${styles.stepBtn} ${styles.stepMinus}`}
                  onClick={() => handleStep(row, -1)}
                  aria-label="Уменьшить количество"
                >
                  <IconMinus size={16} stroke={2} />
                </button>
                <input
                  className={styles.stepValue}
                  type="text"
                  inputMode="numeric"
                  value={String(qty)}
                  onChange={(e) => handleDirectInput(row, e.target.value)}
                  aria-label={`Количество: ${row.displayName}`}
                />
                <button
                  type="button"
                  className={`${styles.stepBtn} ${styles.stepPlus}`}
                  onClick={() => handleStep(row, 1)}
                  aria-label="Увеличить количество"
                >
                  <IconPlus size={16} stroke={2} />
                </button>
              </div>
            ) : (
              <button
                type="button"
                className={styles.addOnlyBtn}
                onClick={() => handleStep(row, 1)}
                aria-label={`Добавить: ${row.displayName}`}
              >
                <IconPlus size={18} stroke={2} />
              </button>
            )}
          </div>
        )
      })}

      {!showAll && filteredRows.length > COLLAPSE_THRESHOLD && (
        <button type="button" className={styles.showAllBtn} onClick={() => setShowAll(true)}>
          Показать все ({filteredRows.length})
        </button>
      )}

      {qtyHintParts.length > 0 && (
        <p className={styles.hint}>
          <IconInfoCircle size={14} stroke={1.8} />
          {qtyHintParts.join(' · ')}
        </p>
      )}

      {lightboxRow != null && (
        <Lightbox
          photos={lightboxPhotos}
          index={lightboxRow}
          onIndexChange={setLightboxRow}
          onClose={() => setLightboxRow(null)}
        />
      )}
    </div>
  )
}

export function variantListSectionTitle(count: number) {
  return count > 1 ? `Варианты · ${count}` : 'Количество'
}
