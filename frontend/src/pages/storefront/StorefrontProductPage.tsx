import { Link, useParams, useSearchParams } from 'react-router-dom'
import { IconChevronLeft, IconShoppingCart, IconHeart, IconHeartFilled, IconCheck } from '@tabler/icons-react'
import { useState, useEffect } from 'react'
import { Button } from '../../shared/ui/Button'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { formatMoney, plural } from '../../shared/lib/format'
import { useStorefrontProduct, useProductReviews } from './product/useProductPageData'
import { ProductLayout } from './product/ProductLayout'
import { Breadcrumbs } from './product/Breadcrumbs'
import { ProductHeader } from './product/ProductHeader'
import { ProductGallery } from './product/ProductGallery'
import { BuyerPhotos } from './product/BuyerPhotos'
import { VariantList, variantListSectionTitle } from './product/VariantList'
import { useSelection } from './product/useSelection'
import { variantPrice, galleryForVariant } from './product/productUtils'
import { addToCart, cartCount, loadCart } from './cart'
import { initialOrderQty } from '../../entities/storefront/api'
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
  const [searchParams] = useSearchParams()
  const highlightVariantId = searchParams.get('v')
  const { product, shopName, loading, error } = useStorefrontProduct(slug, productId)
  const [cartItems, setCartItems] = useState(() => loadCart(slug))
  const [favorites, setFavorites] = useState(() => loadFavorites(slug))
  const { selection, setQty, clear, totalQty, linesCount } = useSelection()
  const [added, setAdded] = useState(false)
  const [activePhoto, setActivePhoto] = useState(0)
  const [toast, setToast] = useState<string | null>(null)
  const { page: reviewsPage } = useProductReviews(slug, productId, {})

  useEffect(() => {
    if (!product) return
    setActivePhoto(0)
    // если в URL указан конкретный вариант — сразу выделяем его фото в галерее
    if (highlightVariantId) {
      const idx = product.variants.findIndex((v) => String(v.id) === highlightVariantId)
      if (idx >= 0 && product.variants[idx].photo) setActivePhoto(0)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 2200)
    return () => clearTimeout(t)
  }, [toast])

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
  const highlightedVariant = product.variants.find((v) => String(v.id) === highlightVariantId)
  const previewVariant =
    highlightedVariant ??
    (selection.size === 1 && product.variants.length > 0
      ? product.variants.find((v) => selection.has(v.id))
      : undefined)
  const previewPrice = previewVariant ? variantPrice(product, previewVariant) : null

  const selectionTotal = Array.from(selection.entries()).reduce((sum, [key, qty]) => {
    const variant = key === 'base' ? undefined : product.variants.find((v) => v.id === key)
    const price = Number(variantPrice(product, variant))
    return sum + price * qty
  }, 0)

  function handleAdd() {
    if (!product || !product.in_stock) return
    if (selection.size === 0) {
      // ничего не выбрано: для товара без вариантов добавляем сразу,
      // для товара с несколькими вариантами — просим выбрать
      if (product.variants.length === 0) {
        addToCart(slug, {
          product_id: product.id,
          name: product.name,
          retail_price: product.retail_price,
          photo: product.photo,
          quantity: String(initialOrderQty(product.min_order_qty, product.order_step_qty)),
          variant_id: null,
        })
        setCartItems(loadCart(slug))
        setAdded(true)
        setToast('Добавлено: 1 товар')
        setTimeout(() => setAdded(false), 1600)
        return
      }
      const firstAvailable = product.variants.find((v) => v.in_stock)
      if (firstAvailable) {
        setQty(firstAvailable.id, initialOrderQty(product.min_order_qty, product.order_step_qty))
      } else {
        setToast('Выберите вариант')
      }
      return
    }
    let count = 0
    for (const [key, qty] of selection.entries()) {
      const variant = key === 'base' ? undefined : product.variants.find((v) => v.id === key)
      addToCart(slug, {
        product_id: product.id,
        name: product.name,
        retail_price: variantPrice(product, variant),
        photo: variant?.photo || product.photo,
        quantity: String(qty),
        variant_id: key === 'base' ? null : key,
        variant_label: variant ? variant.display_name : undefined,
      })
      count += 1
    }
    setCartItems(loadCart(slug))
    clear()
    setAdded(true)
    setToast(`Добавлено: ${count} ${plural(count, ['товар', 'товара', 'товаров'])}`)
    setTimeout(() => setAdded(false), 1600)
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
            <ProductGallery
              photos={galleryForVariant(product, previewVariant)}
              productName={product.name}
              activeIndex={activePhoto}
              onActiveIndexChange={setActivePhoto}
            />
          }
          info={
            <>
              <div className={styles.card}>
                <ProductHeader product={product} selectedPrice={previewPrice} />
              </div>
              <div className={styles.card}>
                <h2 className={styles.sectionTitle} style={{ fontSize: 18, marginBottom: 16 }}>
                  {variantListSectionTitle(product.variants.length)}
                </h2>
                <VariantList
                  product={product}
                  selection={selection}
                  onQtyChange={setQty}
                  onShowToast={setToast}
                />
              </div>
            </>
          }
          aside={
            <div className={styles.card}>
              <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: 20 }}>Итого:</p>
              <p style={{ fontSize: 24, fontWeight: 700, margin: '4px 0 4px' }}>
                {formatMoney(selectionTotal.toFixed(2))} ₽
              </p>
              {linesCount > 0 && (
                <p style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--text-muted)' }}>
                  {totalQty} {plural(totalQty, ['товар', 'товара', 'товаров'])}
                </p>
              )}
              <Button style={{ width: '100%', marginTop: 12 }} onClick={handleAdd} disabled={!product.in_stock}>
                {added ? (
                  <>
                    <IconCheck size={18} stroke={2} /> Добавлено
                  </>
                ) : product.in_stock ? (
                  'В корзину'
                ) : (
                  'Нет в наличии'
                )}
              </Button>
            </div>
          }
          below={
            <>
              <BuyerPhotos photos={reviewsPage?.photos ?? []} />
              {product.description?.trim() && (
                <div className={styles.card}>
                  <h2 className={styles.sectionTitle}>О товаре</h2>
                  <p style={{ whiteSpace: 'pre-line', margin: 0 }}>{product.description}</p>
                </div>
              )}
            </>
          }
        />
      </div>

      {toast && (
        <div className={styles.toast} role="status">
          {toast}
        </div>
      )}
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
