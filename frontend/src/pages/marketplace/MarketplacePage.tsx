import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { IconPackage, IconSearch, IconX } from '@tabler/icons-react'
import {
  listMarketplaceProducts,
  type MarketplaceProduct,
  type MarketplaceSort,
} from '../../entities/marketplace/api'
import { ApiError } from '../../shared/api/client'
import { Select } from '../../shared/ui/Select'
import { Button } from '../../shared/ui/Button'
import { ProductGrid } from '../storefront/ProductGrid'
import styles from '../storefront/Storefront.module.css'

const SORT_OPTIONS: { value: MarketplaceSort; label: string }[] = [
  { value: 'name', label: 'По названию' },
  { value: 'price_asc', label: 'Сначала дешевле' },
  { value: 'price_desc', label: 'Сначала дороже' },
  { value: 'created_desc', label: 'Новинки' },
]

const PAGE_SIZE = 50

export function MarketplacePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const sort = (searchParams.get('sort') as MarketplaceSort) || 'name'
  const shopSlug = searchParams.get('shop_slug') ?? ''
  const category = searchParams.get('category') ?? ''
  const minPrice = searchParams.get('price_min') ?? ''
  const maxPrice = searchParams.get('price_max') ?? ''
  const inStockOnly = searchParams.get('in_stock_only') === 'true'

  const [query, setQuery] = useState(searchParams.get('q') ?? '')
  const [debouncedQuery, setDebouncedQuery] = useState(query)
  const [minPriceDraft, setMinPriceDraft] = useState(minPrice)
  const [maxPriceDraft, setMaxPriceDraft] = useState(maxPrice)
  const [categoryDraft, setCategoryDraft] = useState(category)
  const [products, setProducts] = useState<MarketplaceProduct[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    setMinPriceDraft(minPrice)
    setMaxPriceDraft(maxPrice)
    setCategoryDraft(category)
  }, [minPrice, maxPrice, category])

  function patchParams(patch: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams)
    for (const [k, v] of Object.entries(patch)) {
      if (v == null || v === '') next.delete(k)
      else next.set(k, v)
    }
    setSearchParams(next, { replace: true })
  }

  const listParams = useMemo(
    () => ({
      query: debouncedQuery || undefined,
      category: category || undefined,
      priceMin: minPrice || undefined,
      priceMax: maxPrice || undefined,
      inStockOnly: inStockOnly || undefined,
      shopSlug: shopSlug || undefined,
      sort,
    }),
    [debouncedQuery, category, minPrice, maxPrice, inStockOnly, shopSlug, sort],
  )

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await listMarketplaceProducts({ ...listParams, limit: PAGE_SIZE, offset: 0 })
        if (!cancelled) {
          setProducts(data.products)
          setTotal(data.total)
        }
      } catch (err) {
        if (!cancelled) {
          setProducts([])
          setTotal(0)
          setError(err instanceof ApiError ? err.message : 'Не удалось загрузить каталог')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [listParams])

  async function loadMore() {
    if (loadingMore || products.length >= total) return
    setLoadingMore(true)
    try {
      const data = await listMarketplaceProducts({
        ...listParams,
        limit: PAGE_SIZE,
        offset: products.length,
      })
      setProducts((prev) => [...prev, ...data.products])
      setTotal(data.total)
    } catch {
      /* ignore */
    } finally {
      setLoadingMore(false)
    }
  }

  const shopName = products.find((p) => p.shop_slug === shopSlug)?.shop_name

  const activeFilters: { key: string; label: string; clear: Record<string, string | null> }[] = []
  if (shopSlug) {
    activeFilters.push({
      key: 'shop',
      label: shopName ? `Магазин: ${shopName}` : `Магазин: ${shopSlug}`,
      clear: { shop_slug: null },
    })
  }
  if (minPrice) activeFilters.push({ key: 'min', label: `от ${minPrice} ₽`, clear: { price_min: null } })
  if (maxPrice) activeFilters.push({ key: 'max', label: `до ${maxPrice} ₽`, clear: { price_max: null } })
  if (inStockOnly) activeFilters.push({ key: 'stock', label: 'В наличии', clear: { in_stock_only: null } })
  if (category) activeFilters.push({ key: 'cat', label: category, clear: { category: null } })

  function clearAllFilters() {
    setMinPriceDraft('')
    setMaxPriceDraft('')
    setCategoryDraft('')
    patchParams({
      shop_slug: null,
      price_min: null,
      price_max: null,
      in_stock_only: null,
      category: null,
    })
  }

  function applyCategory(e: FormEvent) {
    e.preventDefault()
    patchParams({ category: categoryDraft.trim() || null })
  }

  return (
    <div className={styles.shell}>
      <h1 className={styles.pageTitle}>Маркетплейс</h1>
      <section className={styles.intro}>
        <p className={styles.introLead}>
          Товары всех магазинов с открытой витриной. Откройте карточку — и перейдите в витрину
          продавца, чтобы оформить заявку.
        </p>
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
          <Select value={sort} onChange={(v) => patchParams({ sort: v })} options={SORT_OPTIONS} />
        </div>

        <div className={styles.filters}>
          <label className={styles.filterField}>
            Цена от
            <input
              type="text"
              inputMode="decimal"
              value={minPriceDraft}
              onChange={(e) => setMinPriceDraft(e.target.value)}
              onBlur={() => patchParams({ price_min: minPriceDraft.trim() || null })}
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
              onBlur={() => patchParams({ price_max: maxPriceDraft.trim() || null })}
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
          <form className={styles.filterField} onSubmit={applyCategory} style={{ minWidth: 140 }}>
            Категория
            <input
              value={categoryDraft}
              onChange={(e) => setCategoryDraft(e.target.value)}
              onBlur={() => patchParams({ category: categoryDraft.trim() || null })}
              placeholder="Обувь"
            />
          </form>
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
      </header>

      <main className={styles.main}>
        {error && <p className={styles.error}>{error}</p>}
        {!loading && !error && (
          <div className={styles.resultMeta}>
            <span>
              Найдено <strong>{total}</strong>
              {products.length < total ? ` · показано ${products.length}` : ''}
            </span>
          </div>
        )}
        {loading ? (
          <ProductGrid items={[]} getHref={() => ''} loading skeletonCount={10} />
        ) : products.length === 0 ? (
          <div className={styles.emptyState}>
            <IconPackage size={36} stroke={1.5} />
            <p>
              {activeFilters.length > 0 || debouncedQuery
                ? 'Ничего не найдено'
                : 'Пока нет магазинов с открытой витриной'}
            </p>
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
          <ProductGrid
            items={products}
            getHref={(item) => `/store/${item.shop_slug}/products/${item.id}`}
            showShop
            onLoadMore={loadMore}
            loadingMore={loadingMore}
            hasMore={products.length < total}
          />
        )}
      </main>
    </div>
  )
}
