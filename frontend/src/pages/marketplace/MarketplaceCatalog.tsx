import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  getMarketplaceCategories,
  getMarketplaceCities,
  listMarketplaceProducts,
  type MarketplaceProduct,
  type MarketplaceSort,
  type PlatformCategory,
} from '../../entities/marketplace/api'
import { ApiError } from '../../shared/api/client'
import { Breadcrumbs } from '../../shared/ui/Breadcrumbs'
import { EmptyState } from '../../shared/ui/EmptyState'
import { FilterBar, type FilterBarValue } from '../storefront/filters/FilterBar'
import { ProductGrid } from '../storefront/ProductGrid'
import styles from './MarketplaceCatalog.module.css'

const SORT_OPTIONS: { value: MarketplaceSort; label: string }[] = [
  { value: 'popular', label: 'Популярные' },
  { value: 'price_asc', label: 'Сначала дешевле' },
  { value: 'price_desc', label: 'Сначала дороже' },
  { value: 'created_desc', label: 'Новинки' },
  { value: 'rating', label: 'По рейтингу' },
  { value: 'discount', label: 'По размеру скидки' },
]

// section → предустановленные параметры (M-F4 §1)
const SECTION_PRESETS: Record<string, { sort?: MarketplaceSort; withDiscount?: boolean; minRating?: number }> = {
  discount: { withDiscount: true, sort: 'discount' },
  popular: { sort: 'popular' },
  new: { sort: 'created_desc' },
  top_rated: { minRating: 4.5, sort: 'rating' },
}

const SECTION_TITLES: Record<string, string> = {
  discount: 'Скидки',
  popular: 'Хиты продаж',
  new: 'Новинки',
  top_rated: 'С высоким рейтингом',
}

const PAGE_SIZE = 24

/** Режим каталога главной /marketplace — есть q/pcat/section/фильтры в URL. M-F4 §1. */
export function MarketplaceCatalog() {
  const [searchParams, setSearchParams] = useSearchParams()

  const query = searchParams.get('q') ?? ''
  const section = searchParams.get('section') ?? ''
  const pcat = searchParams.get('pcat') ?? searchParams.get('category') ?? ''
  const shopSlug = searchParams.get('shop_slug') ?? ''
  // sort явно в URL важнее пресета подборки — иначе подборка навсегда фиксирует сортировку
  const sortParam = searchParams.get('sort') as MarketplaceSort | null
  const preset = section ? SECTION_PRESETS[section] : undefined
  const sort = sortParam || preset?.sort || 'popular'

  const filters: FilterBarValue = {
    minPrice: searchParams.get('price_min') ?? '',
    maxPrice: searchParams.get('price_max') ?? '',
    inStockOnly: searchParams.get('in_stock_only') === 'true',
    variantSize: '',
    variantColor: '',
    minRating: searchParams.get('min_rating')
      ? Number(searchParams.get('min_rating'))
      : preset?.minRating ?? null,
    withDiscount: searchParams.get('with_discount') === 'true' || !!preset?.withDiscount,
    city: searchParams.get('city') ?? '',
  }

  const [products, setProducts] = useState<MarketplaceProduct[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [cities, setCities] = useState<{ name: string; shops_count: number }[]>([])
  const [categories, setCategories] = useState<PlatformCategory[]>([])

  useEffect(() => {
    getMarketplaceCities()
      .then((data) => setCities(data.cities))
      .catch(() => setCities([]))
    getMarketplaceCategories()
      .then((data) => setCategories(data.categories))
      .catch(() => setCategories([]))
  }, [])

  const listParams = useMemo(
    () => ({
      query: query || undefined,
      platformCategory: pcat || undefined,
      city: filters.city || undefined,
      priceMin: filters.minPrice || undefined,
      priceMax: filters.maxPrice || undefined,
      inStockOnly: filters.inStockOnly || undefined,
      withDiscount: filters.withDiscount || undefined,
      minRating: filters.minRating || undefined,
      shopSlug: shopSlug || undefined,
      sort,
    }),
    [
      query,
      pcat,
      filters.city,
      filters.minPrice,
      filters.maxPrice,
      filters.inStockOnly,
      filters.withDiscount,
      filters.minRating,
      shopSlug,
      sort,
    ],
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
      const data = await listMarketplaceProducts({ ...listParams, limit: PAGE_SIZE, offset: products.length })
      setProducts((prev) => [...prev, ...data.products])
      setTotal(data.total)
    } catch {
      /* «Показать ещё» — не критично, просто оставляем как есть при сбое сети */
    } finally {
      setLoadingMore(false)
    }
  }

  /** undefined в значении патча — «не трогать ключ» (в отличие от null — «удалить ключ»). */
  function patchParams(patch: Record<string, string | null | undefined>) {
    const next = new URLSearchParams(searchParams)
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined) continue
      if (v == null || v === '') next.delete(k)
      else next.set(k, v)
    }
    setSearchParams(next, { replace: true })
  }

  function applyFilters(patch: Partial<FilterBarValue>) {
    patchParams({
      price_min: 'minPrice' in patch ? patch.minPrice || null : undefined,
      price_max: 'maxPrice' in patch ? patch.maxPrice || null : undefined,
      in_stock_only: 'inStockOnly' in patch ? (patch.inStockOnly ? 'true' : null) : undefined,
      min_rating: 'minRating' in patch ? (patch.minRating ? String(patch.minRating) : null) : undefined,
      with_discount: 'withDiscount' in patch ? (patch.withDiscount ? 'true' : null) : undefined,
      city: 'city' in patch ? patch.city || null : undefined,
      // ручное изменение фильтра рейтинга/скидки выходит за рамки предустановки подборки —
      // подборка остаётся в URL просто как ярлык истории захода, дальше рулят явные параметры
    })
  }

  function clearAllFilters() {
    patchParams({
      price_min: null,
      price_max: null,
      in_stock_only: null,
      min_rating: null,
      with_discount: null,
      city: null,
    })
  }

  function clearFiltersAndSearch() {
    const next = new URLSearchParams(searchParams)
    for (const key of ['price_min', 'price_max', 'in_stock_only', 'min_rating', 'with_discount', 'city', 'q', 'section', 'pcat', 'category']) {
      next.delete(key)
    }
    setSearchParams(next, { replace: true })
  }

  const hasActiveFilters =
    !!filters.minPrice ||
    !!filters.maxPrice ||
    filters.inStockOnly ||
    !!filters.minRating ||
    !!filters.withDiscount ||
    !!filters.city ||
    !!query ||
    !!pcat

  const filtersEmpty = !loading && products.length === 0
  const activeCategory = pcat ? categories.find((c) => c.slug === pcat) : undefined

  const title = query
    ? `Результаты по запросу «${query}»`
    : section
      ? SECTION_TITLES[section] ?? 'Каталог'
      : activeCategory
        ? activeCategory.name
        : pcat || 'Все товары'

  const crumbLabel = query ? `Поиск: «${query}»` : SECTION_TITLES[section] ?? activeCategory?.name ?? (pcat || 'Каталог')

  return (
    <div className={styles.page}>
      <Breadcrumbs items={[{ label: 'Главная', to: '/marketplace' }, { label: crumbLabel }]} />

      <h1 className={styles.title}>{title}</h1>
      {!loading && <p className={styles.foundCount}>Найдено {total}</p>}

      <FilterBar
        sort={sort}
        sortOptions={SORT_OPTIONS}
        onSortChange={(v) => patchParams({ sort: v })}
        value={filters}
        onChange={applyFilters}
        onClear={clearAllFilters}
        cityOptions={cities.map((c) => ({ value: c.name, label: c.name }))}
        categories={categories.map((c) => ({ id: c.slug, name: c.name, count: c.products_count }))}
        activeCategoryId={pcat || null}
        onCategoryChange={(id) => patchParams({ pcat: id != null ? String(id) : null, category: null })}
        totalCount={total}
        resultCount={total}
      />

      <main>
        {error ? (
          <EmptyState title="Не удалось загрузить каталог" description={error} actionLabel="Повторить" onAction={() => patchParams({})} />
        ) : loading ? (
          <ProductGrid items={[]} getHref={() => ''} loading skeletonCount={12} />
        ) : filtersEmpty ? (
          <EmptyState
            title="Ничего не найдено"
            description="Попробуйте изменить фильтры"
            actionLabel={hasActiveFilters ? 'Сбросить фильтры' : undefined}
            onAction={hasActiveFilters ? clearFiltersAndSearch : undefined}
          />
        ) : (
          <>
            <p className={styles.resultMeta}>
              Показано {products.length} из {total}
            </p>
            <ProductGrid
              items={products}
              getHref={(item) => `/store/${item.shop_slug}/products/${item.id}`}
              showShop
              onLoadMore={loadMore}
              loadingMore={loadingMore}
              hasMore={products.length < total}
            />
          </>
        )}
      </main>
    </div>
  )
}
