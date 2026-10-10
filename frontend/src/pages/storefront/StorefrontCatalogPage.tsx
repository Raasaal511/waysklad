import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  getStorefrontCatalog,
  getStorefrontShopProfileCached,
  peekCachedStorefrontShopProfile,
  initialOrderQty,
  loadRequestToken,
  type CatalogParams,
  type StorefrontCatalog,
  type StorefrontProduct,
  type StorefrontShopProfile,
  type StorefrontSort,
} from '../../entities/storefront/api'
import { ApiError } from '../../shared/api/client'
import { FAVORITES_EVENT, loadFavorites, toggleFavorite } from '../../shared/lib/favorites'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { useScrollRestore } from '../../shared/lib/useScrollRestore'
import { EmptyState } from '../../shared/ui/EmptyState'
import { ErrorState } from '../../shared/ui/ErrorState'
import { ShopHeader, ShopHeaderSkeleton } from './ShopHeader'
import { OwnerStorefrontBar } from './OwnerStorefrontBar'
import { FilterBar, type FilterBarValue } from './filters/FilterBar'
import { addToCart } from './cart'
import { ProductGrid } from './ProductGrid'
import styles from './Storefront.module.css'

const PAGE_SIZE = 24

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
  const filters: FilterBarValue = {
    minPrice: searchParams.get('min_price') ?? '',
    maxPrice: searchParams.get('max_price') ?? '',
    inStockOnly: searchParams.get('in_stock_only') === 'true',
    variantSize: searchParams.get('variant_size') ?? '',
    variantColor: searchParams.get('variant_color') ?? '',
    minRating: searchParams.get('min_rating') ? Number(searchParams.get('min_rating')) : null,
  }
  const query = searchParams.get('q') ?? ''

  const [profile, setProfile] = useState<StorefrontShopProfile | null>(() =>
    peekCachedStorefrontShopProfile(slug),
  )
  const [catalog, setCatalog] = useState<StorefrontCatalog | null>(null)
  const [products, setProducts] = useState<StorefrontProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [errorStatus, setErrorStatus] = useState<number | null>(null)
  // избранное — /store/:slug/favorites; здесь только сердечко на карточке
  const [favorites, setFavorites] = useState<number[]>(() => loadFavorites(slug))
  const requestToken = loadRequestToken(slug)

  // позиция скролла при «назад» из карточки товара — восстанавливаем только когда список
  // реально загружен, не в состоянии skeleton (см. shared/lib/useScrollRestore.ts, P6)
  useScrollRestore(!loading)

  // профиль магазина — отдельный запрос (не входит в ответ каталога), нужен ShopHeader;
  // общий кэш с PublicHeader и карточкой товара — один поход на сервер на весь визит (P7 п.2)
  useEffect(() => {
    let cancelled = false
    getStorefrontShopProfileCached(slug)
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
      title: `${profile.name} — каталог`,
      description: profile.description || `Каталог магазина «${profile.name}»`,
    })
    return () => resetPageMeta()
  }, [profile])

  // избранное меняется и вне каталога — на /store/:slug/favorites и в другой
  // вкладке; перечитываем, чтобы сердечки на карточках не разъезжались
  useEffect(() => {
    function sync() {
      setFavorites(loadFavorites(slug))
    }
    window.addEventListener(FAVORITES_EVENT, sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener(FAVORITES_EVENT, sync)
      window.removeEventListener('storage', sync)
    }
  }, [slug])

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

  function handleToggleFavorite(productId: number) {
    setFavorites(toggleFavorite(slug, productId))
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
      min_order_qty: product.min_order_qty,
      order_step_qty: product.order_step_qty,
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
              ? 'Магазин временно недоступен. Загляните позже.'
              : 'Проверьте ссылку — возможно, в ней опечатка.'
          }
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
  const filtersEmpty = !loading && catalog && products.length === 0 && hasActiveFilters

  return (
    <div className={styles.shell}>
      <OwnerStorefrontBar slug={slug} />
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
            categoriesLoading={loading}
            activeCategoryId={categoryId}
            onCategoryChange={(id) => patchParams({ category_id: id != null ? String(id) : null })}
            totalCount={catalog?.total}
            resultCount={catalog?.total ?? 0}
          />
        </div>
      )}

      <main className={styles.main}>
        {/* h1 — имя магазина (ShopHeader), товары — h3 (ProductCard); без этого h2
            порядок заголовков прыгает через уровень (Lighthouse heading-order) */}
        <h2 className="sr-only">Товары магазина</h2>
        {loading ? (
          <ProductGrid items={[]} getHref={() => ''} loading skeletonCount={8} />
        ) : shopEmpty ? (
          <EmptyState
            illustration="empty-shelf"
            title="В магазине пока нет товаров"
            description="Продавец ещё не выложил товары — загляните позже."
          />
        ) : filtersEmpty ? (
          <EmptyState
            title="Ничего не найдено"
            description="Попробуйте изменить фильтры"
            actionLabel="Сбросить фильтры"
            onAction={clearFiltersAndSearch}
          />
        ) : (
          <>
            {/* «Найдено N» уже есть над фильтрами — второй счётчик нужен, только пока
                показаны не все (подгрузка при прокрутке) */}
            {catalog != null && products.length < catalog.total && (
              <p className={styles.resultMeta}>
                Показано {products.length} из {catalog.total}
              </p>
            )}
            <ProductGrid
              items={products}
              getHref={(item) => `/store/${slug}/products/${item.id}`}
              favorites={favorites}
              onToggleFavorite={(item) => handleToggleFavorite(item.id)}
              onQuickAdd={(item) => quickAdd(item)}
              onLoadMore={loadMore}
              loadingMore={loadingMore}
              hasMore={catalog != null && products.length < catalog.total}
            />
          </>
        )}
      </main>
    </div>
  )
}
