import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  IconSearch,
  IconShoppingCart,
  IconPackage,
  IconHeart,
  IconHeartFilled,
  IconPlus,
  IconX,
  IconBuildingStore,
} from '@tabler/icons-react'
import {
  getStorefrontCatalog,
  initialOrderQty,
  loadRequestToken,
  type StorefrontCatalog,
  type StorefrontProduct,
  type StorefrontSort,
} from '../../entities/storefront/api'
import { ApiError } from '../../shared/api/client'
import { formatMoney, formatQuantity } from '../../shared/lib/format'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { Select } from '../../shared/ui/Select'
import { Button } from '../../shared/ui/Button'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { addToCart, loadCart, cartCount, type StorefrontCartItem } from './cart'
import { CustomerAuthChip, CustomerLoginModal, notifyCustomerAuthChanged } from './CustomerLoginModal'
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
  const [cart, setCart] = useState<StorefrontCartItem[]>(() => loadCart(slug))
  const [favorites, setFavorites] = useState<number[]>(() => loadFavorites(slug))
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
  const [showLogin, setShowLogin] = useState(false)
  const requestToken = loadRequestToken(slug)

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(t)
  }, [query])

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

  useEffect(() => {
    function onStorage() {
      setCart(loadCart(slug))
    }
    window.addEventListener('storage', onStorage)
    window.addEventListener('waysklad:storefront-cart', onStorage)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('waysklad:storefront-cart', onStorage)
    }
  }, [slug])

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
    setCart(loadCart(slug))
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
      <div className={styles.topBar}>
        <div className={styles.topBarInner}>
          <div className={styles.brandBlock}>
            <p className={styles.eyebrow}>Онлайн-витрина</p>
            <h1 className={styles.shopName}>{catalog?.shop_name ?? '…'}</h1>
          </div>
          <div className={styles.headerActions}>
            <Link to="/marketplace" className={styles.marketplaceLink}>
              <IconBuildingStore size={16} stroke={1.8} />
              Все магазины
            </Link>
            <CustomerAuthChip slug={slug} onLoginClick={() => setShowLogin(true)} />
            {requestToken && (
              <Link to={`/store/${slug}/request`} className={styles.headerLink}>
                Мой заказ
              </Link>
            )}
            <Link to={`/store/${slug}/cart`} className={styles.cartBtn} aria-label="Корзина">
              <IconShoppingCart size={20} stroke={1.8} />
              {cartCount(cart) > 0 && <span className={styles.cartBadge}>{cartCount(cart)}</span>}
            </Link>
          </div>
        </div>
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
            {products.map((p, i) => (
              <ProductCard
                key={p.id}
                slug={slug}
                product={p}
                favorite={favorites.includes(p.id)}
                onToggleFavorite={() => toggleFavorite(p.id)}
                onQuickAdd={() => quickAdd(p)}
                style={{ animationDelay: `${Math.min(i, 12) * 40}ms` }}
              />
            ))}
          </div>
        )}
        {catalog && catalog.total > products.length && !showFavoritesOnly && (
          <p className={styles.muted}>Показано {products.length} из {catalog.total}</p>
        )}
      </main>

      {showLogin && (
        <CustomerLoginModal
          onClose={() => setShowLogin(false)}
          onSuccess={() => {
            notifyCustomerAuthChanged()
            setShowLogin(false)
          }}
        />
      )}
    </div>
  )
}

function ProductCard({
  slug,
  product,
  favorite,
  onToggleFavorite,
  onQuickAdd,
  style,
}: {
  slug: string
  product: StorefrontProduct
  favorite: boolean
  onToggleFavorite: () => void
  onQuickAdd: () => void
  style?: CSSProperties
}) {
  return (
    <article className={styles.card} style={style}>
      <Link to={`/store/${slug}/products/${product.id}`} className={styles.cardLink}>
        <div className={styles.cardPhoto}>
          <ProductPhoto src={product.photo} size={48} />
          {!product.in_stock && <span className={styles.outOfStock}>Нет в наличии</span>}
          {Number(product.sold_count ?? 0) > 0 && (
            <span className={styles.soldBadge}>Продано {formatQuantity(product.sold_count!)}</span>
          )}
        </div>
        <div className={styles.cardBody}>
          <h2 className={styles.cardName}>{product.name}</h2>
          <div className={styles.cardFooter}>
            <p className={styles.cardPrice}>{formatMoney(product.retail_price)} ₽</p>
            {product.in_stock && (
              <button
                type="button"
                className={styles.quickAdd}
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  onQuickAdd()
                }}
                aria-label="Добавить в корзину"
              >
                <IconPlus size={16} stroke={2} />
              </button>
            )}
          </div>
        </div>
      </Link>
      <button
        type="button"
        className={styles.favBtn}
        onClick={onToggleFavorite}
        aria-label={favorite ? 'Убрать из избранного' : 'В избранное'}
      >
        {favorite ? <IconHeartFilled size={22} /> : <IconHeart size={22} stroke={1.8} />}
      </button>
    </article>
  )
}
