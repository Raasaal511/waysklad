import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { IconSearch, IconX } from '@tabler/icons-react'
import { listProducts, type Product } from '../entities/product/api'
import { formatMoney } from '../shared/lib/format'
import styles from './GlobalSearch.module.css'

const SUGGEST_LIMIT = 6
const MIN_QUERY_LENGTH = 2
const DEBOUNCE_MS = 250

/** Нормализация для сравнения «введено ровно это»: регистр и лишние пробелы не в счёт. */
function norm(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, ' ')
}

/**
 * Точное совпадение: товар, у которого полностью совпало название, артикул,
 * штрихкод или цифровая часть артикула («СМА-1928463750124» → «1928463750124»).
 * Нужен, чтобы ввод полного названия или артикула вёл сразу на карточку товара,
 * а не на список из одного элемента.
 */
function findExactMatch(items: Product[], query: string): Product | null {
  const q = norm(query)
  if (!q) return null
  const match = items.find((p) => {
    if (norm(p.name) === q) return true
    if (p.sku && norm(p.sku) === q) return true
    if (p.barcode && norm(p.barcode) === q) return true
    // цифровая часть артикула после дефиса — её чаще всего и диктуют
    const skuDigits = p.sku?.split('-').pop() ?? ''
    return skuDigits.length > 0 && norm(skuDigits) === q
  })
  return match ?? null
}

/**
 * Поиск по товарам в шапке кабинета: подсказки с фото, названием и артикулом
 * прямо под строкой. Ищет по названию, артикулу и штрихкоду — в том числе по
 * одной цифровой части артикула (на бэкенде это один ILIKE по склейке
 * name/sku/barcode, см. product_filter._search_text_expr).
 *
 * Enter: при точном совпадении (полное название/артикул/штрихкод) — сразу
 * карточка товара, иначе — список товаров с этим запросом.
 */
export function GlobalSearch() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [items, setItems] = useState<Product[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(-1)
  const wrapRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const trimmed = query.trim()

  useEffect(() => {
    if (trimmed.length < MIN_QUERY_LENGTH) {
      setItems([])
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    const timer = setTimeout(() => {
      listProducts({ query: trimmed, limit: SUGGEST_LIMIT, offset: 0 })
        .then(({ items: found }) => {
          if (!cancelled) {
            setItems(found)
            setHighlighted(-1)
          }
        })
        .catch(() => {
          if (!cancelled) setItems([])
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }, DEBOUNCE_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [trimmed])

  // клик вне компонента закрывает подсказки
  useEffect(() => {
    if (!open) return
    function onPointerDown(e: PointerEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  function reset() {
    setQuery('')
    setItems([])
    setOpen(false)
    setHighlighted(-1)
  }

  function goToProduct(product: Product) {
    reset()
    inputRef.current?.blur()
    navigate(`/products/${product.id}`)
  }

  function submit() {
    if (trimmed.length < MIN_QUERY_LENGTH) return
    // подсвечен конкретный пункт списка — открываем его
    if (highlighted >= 0 && items[highlighted]) {
      goToProduct(items[highlighted])
      return
    }
    // введено полное название/артикул — сразу карточка товара, а не список из одного
    const exact = findExactMatch(items, trimmed)
    if (exact) {
      goToProduct(exact)
      return
    }
    const target = `/products?query=${encodeURIComponent(trimmed)}`
    reset()
    inputRef.current?.blur()
    navigate(target)
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setHighlighted((prev) => (items.length === 0 ? -1 : (prev + 1) % items.length))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlighted((prev) => (items.length === 0 ? -1 : (prev - 1 + items.length) % items.length))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      submit()
    } else if (e.key === 'Escape') {
      setOpen(false)
      setHighlighted(-1)
    }
  }

  const showDropdown = open && trimmed.length >= MIN_QUERY_LENGTH
  const nothingFound = showDropdown && !loading && items.length === 0

  return (
    <div className={styles.wrap} ref={wrapRef}>
      <form
        className={styles.field}
        role="search"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <IconSearch size={18} stroke={1.8} className={styles.icon} />
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder="Поиск по названию, артикулу, штрихкоду…"
          aria-label="Поиск товаров"
          aria-expanded={showDropdown}
          aria-autocomplete="list"
          role="combobox"
          aria-controls="global-search-results"
        />
        {query && (
          <button type="button" className={styles.clear} onClick={reset} aria-label="Очистить поиск">
            <IconX size={16} stroke={2} />
          </button>
        )}
      </form>

      {showDropdown && (
        <div className={styles.dropdown} id="global-search-results" role="listbox">
          {loading && items.length === 0 && (
            <>
              <div className={styles.skeletonRow} />
              <div className={styles.skeletonRow} />
              <div className={styles.skeletonRow} />
            </>
          )}

          {items.map((product, index) => (
            <button
              key={product.id}
              type="button"
              role="option"
              aria-selected={index === highlighted}
              className={`${styles.row} ${index === highlighted ? styles.rowActive : ''}`}
              onMouseEnter={() => setHighlighted(index)}
              onClick={() => goToProduct(product)}
            >
              {product.photo ? (
                <img src={product.photo} alt="" className={styles.photo} width={40} height={40} />
              ) : (
                <span className={`${styles.photo} ${styles.photoEmpty}`} aria-hidden="true" />
              )}
              <span className={styles.texts}>
                <span className={styles.name}>{product.name}</span>
                {product.sku && <span className={styles.sku}>{product.sku}</span>}
              </span>
              <span className={styles.price}>{formatMoney(product.retail_price)}</span>
            </button>
          ))}

          {nothingFound && <p className={styles.empty}>Ничего не найдено</p>}

          {!nothingFound && items.length > 0 && (
            <button type="button" className={styles.allLink} onClick={submit}>
              Показать все результаты
            </button>
          )}
        </div>
      )}
    </div>
  )
}
