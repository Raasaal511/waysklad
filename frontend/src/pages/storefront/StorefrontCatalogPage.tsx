import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  getStorefrontCatalog,
  getStorefrontShopProfile,
  initialOrderQty,
  loadRequestToken,
  type CatalogParams,
  type StorefrontCatalog,
  type StorefrontProduct,
  type StorefrontShopProfile,
  type StorefrontSort,
} from '../../entities/storefront/api'
import { ApiError } from '../../shared/api/client'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { useScrollRestore } from '../../shared/lib/useScrollRestore'
import { MARKETPLACE_PATH } from '../../shared/config'
import { Chip } from '../../shared/ui/Chip'
import { EmptyState } from '../../shared/ui/EmptyState'
import { ErrorState } from '../../shared/ui/ErrorState'
import { ShopHeader, ShopHeaderSkeleton } from './ShopHeader'
import { FilterBar, type FilterBarValue } from './filters/FilterBar'
import { addToCart } from './cart'
import { ProductGrid } from './ProductGrid'
import styles from './Storefront.module.css'

const FAVORITES_KEY = 'waysklad:storefront-favorites'
const PAGE_SIZE = 24

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
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const warehouseId = searchParams.get('warehouse_id')
    ? Number(searchParams.get('warehouse_id'))
    : null
  const sort = (searchParams.get('sort') as StorefrontSort) || 'name'
  const categoryId = searchParams.get('category_id')
    ? Number(searchParams.get('category_id'))
    : null
  const filters: FilterBarValue = {
    minPrice: searchParams.get('min_price') ?? '',
    maxPrice: searchParams.get('max_price') ?? '',
    inStockOnly: searchParams.get('in_stock_only') === 'true',
    variantSize: searchParams.get('variant_size') ?? '',
    variantColor: searchParams.get('variant_color') ?? '',
    minRating: searchParams.get('min_rating') ? Number(searchParams.get('min_rating')) : null,
  }
  const query = searchParams.get('q') ?? ''

  const [profile, setProfile] = useState<StorefrontShopProfile | null>(null)
  const [catalog, setCatalog] = useState<StorefrontCatalog | null>(null)
  const [products, setProducts] = useState<StorefrontProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [errorStatus, setErrorStatus] = useState<number | null>(null)
  const [favorites, setFavorites] = useState<number[]>(() => loadFavorites(slug))
  // ?favorites=1 — используется ссылкой «Избранное» в общей шапке (PublicHeader),
  // чтобы попасть сразу в отфильтрованный вид каталога магазина
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(() => searchParams.get('favorites') === '1')
  const requestToken = loadRequestToken(slug)

  // позиция скролла при «назад» из карточки товара — восстанавливаем только когда список
  // реально загружен, не в состоянии skeleton (см. shared/lib/useScrollRestore.ts, P6)
  useScrollRestore(!loading)

  // профиль магазина — отдельный запрос (не входит в ответ каталога), нужен ShopHeader
  useEffect(() => {
    let cancelled = false
    getStorefrontShopProfile(slug)
      .then((data) => {
        if (!cancelled) setProfile(data)
      })
      .catch((err) => {
        if (cancelled) return
        // каталог и профиль ходят к одной и той же витрине — если профиль 404,
        // основной запрос каталога ниже покажет тот же результат и выставит errorStatus;
        // здесь достаточно молча оставить profile=null (ShopHeader тогда не рендерится)
        if (!(err instanceof ApiError)) return
      })
    return () => {
      cancelled = true
    }
  }, [slug])

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setErrorStatus(null)
      try {
        const params: CatalogParams = {
          query,
          sort,
          categoryId,
          warehouseId,
          minPrice: filters.minPrice || undefined,
          maxPrice: filters.maxPrice || undefined,
          inStockOnly: filters.inStockOnly || undefined,
          variantSize: filters.variantSize || undefined,
          variantColor: filters.variantColor || undefined,
          minRating: filters.minRating || undefined,
          limit: PAGE_SIZE,
          offset: 0,
        }
        const data = await getStorefrontCatalog(slug, params)
        if (!cancelled) {
          setCatalog(data)
          setProducts(data.products)
        }
      } catch (err) {
        if (!cancelled) {
          setCatalog(null)
          setProducts([])
          setErrorStatus(err instanceof ApiError ? err.status : 0)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    slug,
    query,
    sort,
    categoryId,
    warehouseId,
    filters.minPrice,
    filters.maxPrice,
    filters.inStockOnly,
    filters.variantSize,
    filters.variantColor,
    filters.minRating,
  ])

  useEffect(() => {
    if (!profile) return
    setPageMeta({
      title: `${profile.name} — онлайн-витрина`,
      description: profile.description || `Каталог магазина «${profile.name}» на ВайСклад`,
    })
    return () => resetPageMeta()
  }, [profile])

  const visibleProducts = useMemo(() => {
    if (!showFavoritesOnly) return products
    return products.filter((p) => favorites.includes(p.id))
  }, [products, showFavoritesOnly, favorites])

  /** undefined в значении патча — «не трогать ключ» (в отличие от null — «удалить ключ»). */
  function patchParams(patch: Record<string, string | null | undefined>) {
    const next = new URLSearchParams(searchParams)
    for (const [k, v] of Object.entries(patch)) {
      if (v === undefined) continue
      if (v === null || v === '') next.delete(k)
      else next.set(k, v)
    }
    setSearchParams(next, { replace: true })
  }

  function applyFilters(patch: Partial<FilterBarValue>) {
    patchParams({
      min_price: 'minPrice' in patch ? patch.minPrice || null : undefined,
      max_price: 'maxPrice' in patch ? patch.maxPrice || null : undefined,
      in_stock_only: 'inStockOnly' in patch ? (patch.inStockOnly ? 'true' : null) : undefined,
      variant_size: 'variantSize' in patch ? patch.variantSize || null : undefined,
      variant_color: 'variantColor' in patch ? patch.variantColor || null : undefined,
      min_rating: 'minRating' in patch ? (patch.minRating ? String(patch.minRating) : null) : undefined,
    })
  }

  function clearAllFilters() {
    patchParams({
      min_price: null,
      max_price: null,
      in_stock_only: null,
      variant_size: null,
      variant_color: null,
      min_rating: null,
    })
  }

  function clearFiltersAndSearch() {
    const next = new URLSearchParams(searchParams)
    for (const key of ['min_price', 'max_price', 'in_stock_only', 'variant_size', 'variant_color', 'min_rating', 'q']) {
      next.delete(key)
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

  async function loadMore() {
    if (!catalog || loadingMore) return
    setLoadingMore(true)
    try {
      const data = await getStorefrontCatalog(slug, {
        query,
        sort,
        categoryId,
        warehouseId,
        minPrice: filters.minPrice || undefined,
        maxPrice: filters.maxPrice || undefined,
        inStockOnly: filters.inStockOnly || undefined,
        variantSize: filters.variantSize || undefined,
        variantColor: filters.variantColor || undefined,
        minRating: filters.minRating || undefined,
        limit: PAGE_SIZE,
        offset: products.length,
      })
      setProducts((prev) => [...prev, ...data.products])
    } catch {
      // «Показать ещё» — не критично, просто оставляем как есть при сбое сети
    } finally {
      setLoadingMore(false)
    }
  }

  // 404 у публичных /storefront/{slug}* — общий статус и для несуществующей витрины, и
  // для заблокированной (is_suspended): бэкенд не различает их отдельным кодом
  // (backend/app/application/storefront/get_catalog.py:139 — обе причины дают None из
  // use case, роутер превращает в 404 "Витрина не найдена"). Отдельного 403 для
  // публичного каталога нет (403 в shared/api/client.ts — только для сессии сотрудника
  // в кабинете владельца, другой контекст). Ветка errorStatus === 403 ниже — на случай,
  // если статус всё же придёт другим путём (прокси/WAF), не как активный кейс сейчас.
  if (errorStatus != null) {
    return (
      <div className={styles.shell}>
        <ErrorState
          illustration={errorStatus === 403 ? 'error-403-blocked' : 'error-404-not-found'}
          title={errorStatus === 403 ? 'Магазин заблокирован' : 'Витрина не найдена или выключена'}
          description={
            errorStatus === 403
              ? 'Продавец временно заблокирован платформой.'
              : 'Проверьте ссылку или загляните в другие магазины.'
          }
          actionLabel="Все магазины"
          onAction={() => navigate(MARKETPLACE_PATH)}
        />
      </div>
    )
  }

  const hasActiveFilters =
    !!filters.minPrice ||
    !!filters.maxPrice ||
    filters.inStockOnly ||
    !!filters.variantSize ||
    !!filters.variantColor ||
    !!filters.minRating ||
    !!query ||
    categoryId != null

  const shopEmpty = !loading && catalog && catalog.total === 0 && !hasActiveFilters
  const filtersEmpty = !loading && catalog && visibleProducts.length === 0 && (hasActiveFilters || showFavoritesOnly)

  return (
    <div className={styles.shell}>
      {loading && !profile ? <ShopHeaderSkeleton /> : profile ? <ShopHeader profile={profile} /> : null}

      {requestToken && (
        <div className={styles.catalogTopRow}>
          <Link to={`/store/${slug}/request`} className={styles.headerLink}>
            Мой заказ
          </Link>
        </div>
      )}

      {!shopEmpty && (
        <div className={styles.header}>
          <FilterBar
            sort={sort}
            sortOptions={SORT_OPTIONS}
            onSortChange={(v) => patchParams({ sort: v })}
            value={filters}
            onChange={applyFilters}
            onClear={clearAllFilters}
            availableSizes={catalog?.available_sizes ?? []}
            availableColors={catalog?.available_colors ?? []}
            categories={(catalog?.categories ?? []).map((c) => ({ id: c.id, name: c.name, count: c.product_count }))}
            activeCategoryId={categoryId}
            onCategoryChange={(id) => {
              setShowFavoritesOnly(false)
              patchParams({ category_id: id != null ? String(id) : null })
            }}
            totalCount={catalog?.total}
            resultCount={catalog?.total ?? 0}
          />
          {favorites.length > 0 && (
            <Chip active={showFavoritesOnly} className={styles.favoritesChip} onClick={() => setShowFavoritesOnly((v) => !v)}>
              Избранное · {favorites.length}
            </Chip>
          )}
        </div>
      )}

      <main className={styles.main}>
        {loading ? (
          <ProductGrid items={[]} getHref={() => ''} loading skeletonCount={8} />
        ) : shopEmpty ? (
          <EmptyState
            illustration="empty-shelf"
            title="В магазине пока нет товаров"
            actionLabel="Все магазины"
            onAction={() => navigate(MARKETPLACE_PATH)}
          />
        ) : filtersEmpty ? (
          <EmptyState
            title="Ничего не найдено"
            description="Попробуйте изменить фильтры"
            actionLabel="Сбросить фильтры"
            onAction={() => {
              setShowFavoritesOnly(false)
              clearFiltersAndSearch()
            }}
          />
        ) : (
          <>
            <p className={styles.resultMeta}>
              {showFavoritesOnly
                ? `Избранное · ${visibleProducts.length}`
                : `Показано ${products.length} из ${catalog?.total ?? products.length}`}
            </p>
            <ProductGrid
              items={visibleProducts}
              getHref={(item) => `/store/${slug}/products/${item.id}`}
              favorites={favorites}
              onToggleFavorite={(item) => toggleFavorite(item.id)}
              onQuickAdd={(item) => quickAdd(item)}
              onLoadMore={!showFavoritesOnly ? loadMore : undefined}
              loadingMore={loadingMore}
              hasMore={!showFavoritesOnly && catalog != null && products.length < catalog.total}
            />
          </>
        )}
      </main>
    </div>
  )
}
