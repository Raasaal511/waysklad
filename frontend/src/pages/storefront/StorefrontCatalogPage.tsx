import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { IconSearch, IconPackage, IconX } from '@tabler/icons-react'
import {
  getStorefrontCatalog,
  initialOrderQty,
  loadRequestToken,
  type StorefrontCatalog,
  type StorefrontProduct,
  type StorefrontSort,
} from '../../entities/storefront/api'
import { ApiError } from '../../shared/api/client'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { Select } from '../../shared/ui/Select'
import { Button } from '../../shared/ui/Button'
import { addToCart } from './cart'
import { ProductCard } from './ProductCard'
import styles from './Storefront.module.css'

const FAVORITES_KEY = 'waysklad:storefront-favorites'

function loadFavorites(slug: string): number[] {
  try {
    const raw = localStorage.getItem(`${FAVORITES_KEY}:${slug}`)
    return raw ? (JSON.parse(raw) as number[]) : []
  } catch {
    return []
  }
}

function saveFavorites(slug: string, ids: number[]) {
  localStorage.setItem(`${FAVORITES_KEY}:${slug}`, JSON.stringify(ids))
}

const SORT_OPTIONS: { value: StorefrontSort; label: string }[] = [
  { value: 'name', label: 'По названию' },
  { value: 'price_asc', label: 'Сначала дешевле' },
  { value: 'price_desc', label: 'Сначала дороже' },
  { value: 'created_desc', label: 'Новинки' },
]

export function StorefrontCatalogPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const warehouseId = searchParams.get('warehouse_id')
    ? Number(searchParams.get('warehouse_id'))
    : null
  const sort = (searchParams.get('sort') as StorefrontSort) || 'name'
  const categoryId = searchParams.get('category_id')
    ? Number(searchParams.get('category_id'))
    : null
  const minPrice = searchParams.get('min_price') ?? ''
  const maxPrice = searchParams.get('max_price') ?? ''
  const inStockOnly = searchParams.get('in_stock_only') === 'true'
  const variantSize = searchParams.get('variant_size') ?? ''
  const variantColor = searchParams.get('variant_color') ?? ''

  const [query, setQuery] = useState(searchParams.get('q') ?? '')
  const [debouncedQuery, setDebouncedQuery] = useState(query)
  const [minPriceDraft, setMinPriceDraft] = useState(minPrice)
  const [maxPriceDraft, setMaxPriceDraft] = useState(maxPrice)
  const [catalog, setCatalog] = useState<StorefrontCatalog | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [favorites, setFavorites] = useState<number[]>(() => loadFavorites(slug))
  // ?favorites=1 — используется ссылкой «Избранное» в общей шапке (PublicHeader),
  // чтобы попасть сразу в отфильтрованный вид каталога магазина
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(() => searchParams.get('favorites') === '1')
  const requestToken = loadRequestToken(slug)

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(t)
  }, [query])

  // ?q= может измениться извне (поиск в общей шапке PublicHeader), не только
  // через локальное поле ввода на этой странице — держим их в синхронизации
  useEffect(() => {
    const urlQuery = searchParams.get('q') ?? ''
    setQuery((prev) => (prev === urlQuery ? prev : urlQuery))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams.get('q')])

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await getStorefrontCatalog(slug, {
          query: debouncedQuery,
          sort,
          categoryId,
          warehouseId,
          minPrice: minPrice || undefined,
          maxPrice: maxPrice || undefined,
          inStockOnly: inStockOnly || undefined,
          variantSize: variantSize || undefined,
          variantColor: variantColor || undefined,
          limit: 50,
        })
        if (!cancelled) setCatalog(data)
      } catch (err) {
        if (!cancelled) {
          setCatalog(null)
          setError(
            err instanceof ApiError && err.status === 404
              ? 'Витрина не найдена или выключена'
              : err instanceof ApiError
                ? err.message
                : 'Не удалось загрузить витрину',
          )
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [
    slug,
    debouncedQuery,
    sort,
    categoryId,
    warehouseId,
    minPrice,
    maxPrice,
    inStockOnly,
    variantSize,
    variantColor,
  ])

  useEffect(() => {
    if (!catalog?.shop_name) return
    setPageMeta({
      title: `${catalog.shop_name} · WaySklad`,
      description: `Каталог магазина «${catalog.shop_name}»`,
    })
    return () => resetPageMeta()
  }, [catalog?.shop_name])

  useEffect(() => {
    setMinPriceDraft(minPrice)
    setMaxPriceDraft(maxPrice)
  }, [minPrice, maxPrice])

  const products = useMemo(() => {
    const list = catalog?.products ?? []
    if (!showFavoritesOnly) return list
    return list.filter((p) => favorites.includes(p.id))
  }, [catalog, showFavoritesOnly, favorites])

  function patchParams(patch: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams)
    for (const [k, v] of Object.entries(patch)) {
      if (v == null || v === '') next.delete(k)
      else next.set(k, v)
    }
    setSearchParams(next, { replace: true })
  }

  function toggleFavorite(productId: number) {
    setFavorites((prev) => {
      const next = prev.includes(productId)
        ? prev.filter((id) => id !== productId)
        : [...prev, productId]
      saveFavorites(slug, next)
      return next
    })
  }

  function quickAdd(product: StorefrontProduct) {
    if (!product.in_stock) return
    addToCart(slug, {
      product_id: product.id,
      name: product.name,
      retail_price: product.retail_price,
      photo: product.photo,
      quantity: String(initialOrderQty(product.min_order_qty, product.order_step_qty)),
      variant_id: null,
    })
  }

  const activeFilters: { key: string; label: string; clear: Record<string, string | null> }[] = []
  if (minPrice) activeFilters.push({ key: 'min', label: `от ${minPrice} ₽`, clear: { min_price: null } })
  if (maxPrice) activeFilters.push({ key: 'max', label: `до ${maxPrice} ₽`, clear: { max_price: null } })
  if (inStockOnly) activeFilters.push({ key: 'stock', label: 'В наличии', clear: { in_stock_only: null } })
  if (variantSize) activeFilters.push({ key: 'size', label: `Размер ${variantSize}`, clear: { variant_size: null } })
  if (variantColor) activeFilters.push({ key: 'color', label: variantColor, clear: { variant_color: null } })
  if (warehouseId != null) {
    const wh = catalog?.warehouses.find((w) => w.id === warehouseId)
    activeFilters.push({
      key: 'wh',
      label: wh?.name ?? `Точка #${warehouseId}`,
      clear: { warehouse_id: null },
    })
  }

  function clearAllFilters() {
    setMinPriceDraft('')
    setMaxPriceDraft('')
    patchParams({
      min_price: null,
      max_price: null,
      in_stock_only: null,
      variant_size: null,
      variant_color: null,
      warehouse_id: null,
    })
  }

  if (error && !catalog) {
    return (
      <div className={styles.shell}>
        <div className={styles.emptyState}>
          <IconPackage size={40} stroke={1.5} />
          <h1>Витрина недоступна</h1>
          <p>{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.shell}>
      <div className={styles.catalogTopRow}>
        <h1 className={styles.pageTitle}>{catalog?.shop_name ?? '…'}</h1>
        {requestToken && (
          <Link to={`/store/${slug}/request`} className={styles.headerLink}>
            Мой заказ
          </Link>
        )}
      </div>

      <section className={styles.intro}>
        <p className={styles.introLead}>Выберите товары и оформите заказ — магазин подтвердит наличие.</p>
      </section>

      <header className={styles.header}>
        <div className={styles.toolbar}>
          <label className={styles.search}>
            <IconSearch size={16} stroke={1.8} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Найти товар…"
            />
          </label>
          <Select
            value={sort}
            onChange={(v) => patchParams({ sort: v })}
            options={SORT_OPTIONS}
          />
        </div>

        <div className={styles.filters}>
          <label className={styles.filterField}>
            Цена от
            <input
              type="text"
              inputMode="decimal"
              value={minPriceDraft}
              onChange={(e) => setMinPriceDraft(e.target.value)}
              onBlur={() => patchParams({ min_price: minPriceDraft.trim() || null })}
              placeholder="0"
            />
          </label>
          <label className={styles.filterField}>
            до
            <input
              type="text"
              inputMode="decimal"
              value={maxPriceDraft}
              onChange={(e) => setMaxPriceDraft(e.target.value)}
              onBlur={() => patchParams({ max_price: maxPriceDraft.trim() || null })}
              placeholder="∞"
            />
          </label>
          <label className={styles.filterCheck}>
            <input
              type="checkbox"
              checked={inStockOnly}
              onChange={(e) => patchParams({ in_stock_only: e.target.checked ? 'true' : null })}
            />
            Только в наличии
          </label>
          {(catalog?.available_sizes.length ?? 0) > 0 && (
            <Select
              value={variantSize}
              onChange={(v) => patchParams({ variant_size: v || null })}
              options={[
                { value: '', label: 'Размер' },
                ...(catalog?.available_sizes.map((s) => ({ value: s, label: s })) ?? []),
              ]}
            />
          )}
          {(catalog?.available_colors.length ?? 0) > 0 && (
            <Select
              value={variantColor}
              onChange={(v) => patchParams({ variant_color: v || null })}
              options={[
                { value: '', label: 'Цвет' },
                ...(catalog?.available_colors.map((c) => ({ value: c, label: c })) ?? []),
              ]}
            />
          )}
          {(catalog?.warehouses.length ?? 0) > 1 && (
            <Select
              value={warehouseId != null ? String(warehouseId) : ''}
              onChange={(v) => patchParams({ warehouse_id: v || null })}
              options={[
                { value: '', label: 'Все точки' },
                ...(catalog?.warehouses.map((w) => ({ value: String(w.id), label: w.name })) ?? []),
              ]}
            />
          )}
        </div>

        {activeFilters.length > 0 && (
          <div className={styles.filterChips}>
            {activeFilters.map((f) => (
              <button
                key={f.key}
                type="button"
                className={styles.filterChip}
                onClick={() => patchParams(f.clear)}
              >
                {f.label}
                <IconX size={12} stroke={2} />
              </button>
            ))}
            <button type="button" className={styles.filterChipClear} onClick={clearAllFilters}>
              Сбросить
            </button>
          </div>
        )}

        {((catalog?.categories.length ?? 0) > 0 || favorites.length > 0) && (
          <div className={styles.categories}>
            <button
              type="button"
              className={!categoryId && !showFavoritesOnly ? styles.catActive : styles.cat}
              onClick={() => {
                setShowFavoritesOnly(false)
                patchParams({ category_id: null })
              }}
            >
              Все
            </button>
            {catalog?.categories.map((c) => (
              <button
                key={c.id}
                type="button"
                className={categoryId === c.id && !showFavoritesOnly ? styles.catActive : styles.cat}
                onClick={() => {
                  setShowFavoritesOnly(false)
                  patchParams({ category_id: String(c.id) })
                }}
              >
                {c.name} · {c.product_count}
              </button>
            ))}
            <button
              type="button"
              className={showFavoritesOnly ? styles.catActive : styles.cat}
              onClick={() => setShowFavoritesOnly((v) => !v)}
            >
              Избранное{favorites.length > 0 ? ` · ${favorites.length}` : ''}
            </button>
          </div>
        )}
      </header>

      <main className={styles.main}>
        {catalog && !loading && (
          <div className={styles.resultMeta}>
            <span>
              {showFavoritesOnly
                ? `Избранное · ${products.length}`
                : (
                  <>
                    Найдено <strong>{catalog.total}</strong>
                    {products.length < catalog.total ? ` · показано ${products.length}` : ''}
                  </>
                )}
            </span>
          </div>
        )}
        {loading && !catalog ? (
          <p className={styles.muted}>Загрузка…</p>
        ) : products.length === 0 ? (
          <div className={styles.emptyState}>
            <IconPackage size={36} stroke={1.5} />
            <p>{activeFilters.length > 0 || debouncedQuery ? 'Ничего не найдено' : 'Пока нет товаров'}</p>
            {(activeFilters.length > 0 || debouncedQuery) && (
              <Button
                variant="secondary"
                onClick={() => {
                  setQuery('')
                  clearAllFilters()
                }}
              >
                Сбросить поиск и фильтры
              </Button>
            )}
          </div>
        ) : (
          <div className={styles.grid}>
            {products.map((p) => (
              <ProductCard
                key={p.id}
                item={p}
                href={`/store/${slug}/products/${p.id}`}
                favorite={favorites.includes(p.id)}
                onToggleFavorite={() => toggleFavorite(p.id)}
                onQuickAdd={() => quickAdd(p)}
              />
            ))}
          </div>
        )}
        {catalog && catalog.total > products.length && !showFavoritesOnly && (
          <p className={styles.muted}>Показано {products.length} из {catalog.total}</p>
        )}
      </main>
    </div>
  )
}
