import { Link, useParams } from 'react-router-dom'
import { IconChevronLeft, IconShoppingCart, IconHeart, IconHeartFilled } from '@tabler/icons-react'
import { useState, useEffect } from 'react'
import { Button } from '../../shared/ui/Button'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { formatMoney } from '../../shared/lib/format'
import { useStorefrontProduct } from './product/useProductPageData'
import { ProductLayout } from './product/ProductLayout'
import { Breadcrumbs } from './product/Breadcrumbs'
import { ProductHeader } from './product/ProductHeader'
import { variantPrice } from './product/productUtils'
import { addToCart, cartCount, loadCart } from './cart'
import { initialOrderQty, bumpOrderQty } from '../../entities/storefront/api'
import shellStyles from './Storefront.module.css'
import styles from './product/ProductPage.module.css'

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

export function StorefrontProductPage() {
  const { slug = '', productId = '' } = useParams<{ slug: string; productId: string }>()
  const { product, shopName, loading, error } = useStorefrontProduct(slug, productId)
  const [cartItems, setCartItems] = useState(() => loadCart(slug))
  const [favorites, setFavorites] = useState(() => loadFavorites(slug))
  const [variantId, setVariantId] = useState<number | null>(null)
  const [qty, setQty] = useState(1)
  const [added, setAdded] = useState(false)

  useEffect(() => {
    if (!product) return
    setVariantId(product.variants[0]?.id ?? null)
    setQty(initialOrderQty(product.min_order_qty, product.order_step_qty))
  }, [product])

  useEffect(() => {
    if (!product || !shopName) return
    setPageMeta({
      title: `${product.name} · ${shopName}`,
      description: product.description?.trim() || `${formatMoney(product.retail_price)} ₽ · ${shopName}`,
    })
    return () => resetPageMeta()
  }, [product, shopName])

  useEffect(() => {
    function sync() {
      setCartItems(loadCart(slug))
    }
    window.addEventListener('waysklad:storefront-cart', sync)
    return () => window.removeEventListener('waysklad:storefront-cart', sync)
  }, [slug])

  function toggleFavorite() {
    if (!product) return
    setFavorites((prev) => {
      const next = prev.includes(product.id) ? prev.filter((id) => id !== product.id) : [...prev, product.id]
      saveFavorites(slug, next)
      return next
    })
  }

  if (loading) {
    return (
      <div className={styles.page}>
        <TopBar
          slug={slug}
          shopName={shopName}
          cartCount={cartCount(cartItems)}
          favoritesCount={favorites.length}
          isFavorite={false}
          onToggleFavorite={undefined}
        />
        <div className={styles.container}>
          <p style={{ padding: '32px 0', color: 'var(--text-muted)' }}>Загрузка…</p>
        </div>
      </div>
    )
  }

  if (error || !product) {
    return (
      <div className={styles.page}>
        <TopBar
          slug={slug}
          shopName={shopName}
          cartCount={cartCount(cartItems)}
          favoritesCount={favorites.length}
          isFavorite={false}
          onToggleFavorite={undefined}
        />
        <div className={styles.container}>
          <div className={shellStyles.emptyState}>
            <p>{error ?? 'Товар не найден'}</p>
            <Link to={`/store/${slug}`}>
              <Button>Вернуться в витрину</Button>
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const isFavorite = favorites.includes(product.id)
  const selectedVariant = product.variants.find((v) => v.id === variantId)
  const unitPrice = variantPrice(product, selectedVariant)
  const minOrderQty = product.min_order_qty
  const orderStepQty = product.order_step_qty
  const minQty = initialOrderQty(minOrderQty, orderStepQty)

  function handleAdd() {
    if (!product || !product.in_stock) return
    const variant = product.variants.find((v) => v.id === variantId)
    addToCart(slug, {
      product_id: product.id,
      name: product.name,
      retail_price: variantPrice(product, variant),
      photo: variant?.photo || product.photo,
      quantity: String(qty),
      variant_id: variantId,
      variant_label: variant ? variant.display_name : undefined,
    })
    setCartItems(loadCart(slug))
    setAdded(true)
    setTimeout(() => setAdded(false), 1600)
  }

  function bump(deltaSteps: number) {
    setQty((q) => bumpOrderQty(q, deltaSteps, minOrderQty, orderStepQty))
  }

  return (
    <div className={styles.page}>
      <TopBar
        slug={slug}
        shopName={shopName}
        cartCount={cartCount(cartItems)}
        favoritesCount={favorites.length}
        isFavorite={isFavorite}
        onToggleFavorite={toggleFavorite}
      />
      <div className={styles.container}>
        <Breadcrumbs slug={slug} category={product.category} />

        <ProductLayout
          gallery={
            <div className={styles.card}>
              {product.storefront_photos[0] || product.photo ? (
                <img
                  src={product.storefront_photos[0] || product.photo}
                  alt={product.name}
                  style={{ width: '100%', borderRadius: 16, aspectRatio: '4 / 5', objectFit: 'cover' }}
                />
              ) : (
                <div
                  style={{
                    width: '100%',
                    aspectRatio: '4 / 5',
                    borderRadius: 16,
                    background: 'var(--bg-muted)',
                  }}
                />
              )}
            </div>
          }
          info={
            <div className={styles.card}>
              <ProductHeader product={product} selectedPrice={selectedVariant ? unitPrice : null} />
              <div style={{ marginTop: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
                <button type="button" onClick={() => bump(-1)} disabled={qty <= minQty} aria-label="Меньше">
                  −
                </button>
                <span>{qty}</span>
                <button type="button" onClick={() => bump(1)} disabled={qty >= 9999} aria-label="Больше">
                  +
                </button>
              </div>
            </div>
          }
          aside={
            <div className={styles.card}>
              <p style={{ margin: 0, color: 'var(--text-muted)' }}>Итого</p>
              <p style={{ fontSize: 24, fontWeight: 700, margin: '4px 0 12px' }}>
                {formatMoney((Number(unitPrice) * qty).toFixed(2))} ₽
              </p>
              <Button style={{ width: '100%' }} onClick={handleAdd} disabled={!product.in_stock}>
                {added ? 'Добавлено' : 'В корзину'}
              </Button>
            </div>
          }
          below={
            product.description?.trim() ? (
              <div className={styles.card}>
                <h2 className={styles.sectionTitle}>О товаре</h2>
                <p style={{ whiteSpace: 'pre-line', margin: 0 }}>{product.description}</p>
              </div>
            ) : null
          }
        />
      </div>
    </div>
  )
}

function TopBar({
  slug,
  shopName,
  cartCount: count,
  favoritesCount,
  isFavorite,
  onToggleFavorite,
}: {
  slug: string
  shopName: string
  cartCount: number
  favoritesCount: number
  isFavorite: boolean
  onToggleFavorite: (() => void) | undefined
}) {
  return (
    <div className={shellStyles.topBar}>
      <div className={shellStyles.topBarInner}>
        <Link to={`/store/${slug}`} className={shellStyles.back}>
          <IconChevronLeft size={18} stroke={1.8} />
          <span className={shellStyles.backShop}>{shopName || 'Магазин'}</span>
        </Link>
        <div className={shellStyles.headerActions}>
          <button
            type="button"
            className={shellStyles.iconGhost}
            onClick={onToggleFavorite}
            disabled={!onToggleFavorite}
            aria-label={isFavorite ? 'Убрать из избранного' : 'В избранное'}
          >
            {isFavorite ? <IconHeartFilled size={20} /> : <IconHeart size={20} stroke={1.8} />}
            {favoritesCount > 0 && <span className={shellStyles.cartBadge}>{favoritesCount}</span>}
          </button>
          <Link to={`/store/${slug}/cart`} className={shellStyles.cartBtn} aria-label="Корзина">
            <IconShoppingCart size={20} stroke={1.8} />
            {count > 0 && <span className={shellStyles.cartBadge}>{count}</span>}
          </Link>
        </div>
      </div>
    </div>
  )
}
