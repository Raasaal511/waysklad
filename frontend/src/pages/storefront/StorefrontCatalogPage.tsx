import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  IconSearch,
  IconShoppingCart,
  IconPackage,
  IconHeart,
  IconHeartFilled,
  IconPlus,
} from '@tabler/icons-react'
import {
  getStorefrontCatalog,
  loadRequestToken,
  type StorefrontCatalog,
  type StorefrontProduct,
  type StorefrontSort,
} from '../../entities/storefront/api'
import { ApiError } from '../../shared/api/client'
import { formatMoney } from '../../shared/lib/format'
import { Select } from '../../shared/ui/Select'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { addToCart, loadCart, cartCount, type StorefrontCartItem } from './cart'
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

  const [query, setQuery] = useState(searchParams.get('q') ?? '')
  const [debouncedQuery, setDebouncedQuery] = useState(query)
  const [catalog, setCatalog] = useState<StorefrontCatalog | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cart, setCart] = useState<StorefrontCartItem[]>(() => loadCart(slug))
  const [favorites, setFavorites] = useState<number[]>(() => loadFavorites(slug))
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
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
  }, [slug, debouncedQuery, sort, categoryId, warehouseId])

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
      quantity: '1',
      variant_id: null,
    })
    setCart(loadCart(slug))
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
            {requestToken && (
              <Link to={`/store/${slug}/request`} className={styles.headerLink}>
                Моя заявка
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
        <p className={styles.introLead}>Выберите товары и оставьте заявку — магазин подтвердит наличие.</p>
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
        {loading && !catalog ? (
          <p className={styles.muted}>Загрузка…</p>
        ) : products.length === 0 ? (
          <div className={styles.emptyState}>
            <IconPackage size={36} stroke={1.5} />
            <p>Пока нет товаров</p>
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
        {favorite ? <IconHeartFilled size={18} /> : <IconHeart size={18} stroke={1.8} />}
      </button>
    </article>
  )
}
