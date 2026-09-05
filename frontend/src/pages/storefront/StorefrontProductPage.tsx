import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  IconChevronLeft,
  IconShoppingCart,
  IconMinus,
  IconPlus,
  IconCheck,
  IconHeart,
  IconHeartFilled,
} from '@tabler/icons-react'
import {
  getStorefrontProduct,
  type StorefrontProductDetail,
} from '../../entities/storefront/api'
import { ApiError } from '../../shared/api/client'
import { formatMoney } from '../../shared/lib/format'
import { Button } from '../../shared/ui/Button'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { addToCart, cartCount, loadCart } from './cart'
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

export function StorefrontProductPage() {
  const { slug = '', productId = '' } = useParams<{ slug: string; productId: string }>()
  const navigate = useNavigate()
  const [product, setProduct] = useState<StorefrontProductDetail | null>(null)
  const [shopName, setShopName] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [qty, setQty] = useState(1)
  const [variantId, setVariantId] = useState<number | null>(null)
  const [added, setAdded] = useState(false)
  const [cartItems, setCartItems] = useState(() => loadCart(slug))
  const [favorites, setFavorites] = useState(() => loadFavorites(slug))

  const isFavorite = product ? favorites.includes(product.id) : false

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const data = await getStorefrontProduct(slug, Number(productId))
        if (cancelled) return
        setShopName(data.shop_name)
        setProduct(data.product)
        setVariantId(data.product.variants[0]?.id ?? null)
        setQty(1)
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError && err.status === 404
              ? 'Товар не найден'
              : err instanceof ApiError
                ? err.message
                : 'Не удалось загрузить товар',
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
  }, [slug, productId])

  useEffect(() => {
    function sync() {
      setCartItems(loadCart(slug))
    }
    window.addEventListener('waysklad:storefront-cart', sync)
    return () => window.removeEventListener('waysklad:storefront-cart', sync)
  }, [slug])

  function bump(delta: number) {
    setQty((q) => Math.max(1, Math.min(999, q + delta)))
  }

  function toggleFavorite() {
    if (!product) return
    setFavorites((prev) => {
      const next = prev.includes(product.id)
        ? prev.filter((id) => id !== product.id)
        : [...prev, product.id]
      saveFavorites(slug, next)
      return next
    })
  }

  function handleAdd() {
    if (!product || !product.in_stock) return
    const variant = product.variants.find((v) => v.id === variantId)
    addToCart(slug, {
      product_id: product.id,
      name: product.name,
      retail_price: product.retail_price,
      photo: product.photo,
      quantity: String(qty),
      variant_id: variantId,
      variant_label: variant ? [variant.size, variant.color].filter(Boolean).join(' / ') : undefined,
    })
    setCartItems(loadCart(slug))
    setAdded(true)
    setTimeout(() => setAdded(false), 1600)
  }

  if (loading) {
    return (
      <div className={styles.shell}>
        <div className={styles.emptyState}>
          <p className={styles.muted}>Загрузка…</p>
        </div>
      </div>
    )
  }

  if (error || !product) {
    return (
      <div className={styles.shell}>
        <div className={styles.topBar}>
          <div className={styles.topBarInner}>
            <Link to={`/store/${slug}`} className={styles.back}>
              <IconChevronLeft size={18} stroke={1.8} /> К каталогу
            </Link>
          </div>
        </div>
        <div className={styles.emptyState}>
          <p>{error ?? 'Товар не найден'}</p>
          <Link to={`/store/${slug}`}>
            <Button>Вернуться в витрину</Button>
          </Link>
        </div>
      </div>
    )
  }

  const lineTotal = (Number(product.retail_price) * qty).toFixed(2)

  return (
    <div className={styles.shell}>
      <div className={styles.topBar}>
        <div className={styles.topBarInner}>
          <Link to={`/store/${slug}`} className={styles.back}>
            <IconChevronLeft size={18} stroke={1.8} />
            <span className={styles.backShop}>{shopName}</span>
          </Link>
          <div className={styles.headerActions}>
            <button
              type="button"
              className={styles.iconGhost}
              onClick={toggleFavorite}
              aria-label={isFavorite ? 'Убрать из избранного' : 'В избранное'}
            >
              {isFavorite ? <IconHeartFilled size={20} /> : <IconHeart size={20} stroke={1.8} />}
            </button>
            <Link to={`/store/${slug}/cart`} className={styles.cartBtn} aria-label="Корзина">
              <IconShoppingCart size={20} stroke={1.8} />
              {cartCount(cartItems) > 0 && (
                <span className={styles.cartBadge}>{cartCount(cartItems)}</span>
              )}
            </Link>
          </div>
        </div>
      </div>

      <main className={styles.productPage}>
        <div className={styles.productHero}>
          <ProductPhoto src={product.photo} size={56} />
          {!product.in_stock && <span className={styles.heroBadge}>Нет в наличии</span>}
        </div>

        <div className={styles.productInfo}>
          <div className={styles.productHead}>
            {product.sku && <span className={styles.skuChip}>арт. {product.sku}</span>}
            <h1>{product.name}</h1>
            <p className={styles.productPrice}>{formatMoney(product.retail_price)} ₽</p>
            {product.in_stock ? (
              <span className={styles.inStockChip}>В наличии</span>
            ) : (
              <span className={styles.outBadge}>Нет в наличии</span>
            )}
          </div>

          {product.variants.length > 0 && (
            <div className={styles.optionBlock}>
              <span className={styles.optionLabel}>Вариант</span>
              <div className={styles.variantGrid}>
                {product.variants.map((v) => {
                  const label = [v.size, v.color].filter(Boolean).join(' · ') || `#${v.id}`
                  const active = variantId === v.id
                  return (
                    <button
                      key={v.id}
                      type="button"
                      className={active ? styles.variantChipActive : styles.variantChip}
                      onClick={() => setVariantId(v.id)}
                    >
                      {label}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          <div className={styles.optionBlock}>
            <span className={styles.optionLabel}>Количество</span>
            <div className={styles.qtyStepper}>
              <button
                type="button"
                className={styles.qtyBtn}
                onClick={() => bump(-1)}
                disabled={qty <= 1}
                aria-label="Меньше"
              >
                <IconMinus size={18} stroke={2} />
              </button>
              <input
                className={styles.qtyValue}
                type="text"
                inputMode="numeric"
                value={String(qty)}
                onChange={(e) => {
                  const digits = e.target.value.replace(/\D/g, '')
                  if (digits === '') {
                    setQty(1)
                    return
                  }
                  setQty(Math.max(1, Math.min(999, Number(digits))))
                }}
                aria-label="Количество"
              />
              <button
                type="button"
                className={styles.qtyBtn}
                onClick={() => bump(1)}
                disabled={qty >= 999}
                aria-label="Больше"
              >
                <IconPlus size={18} stroke={2} />
              </button>
            </div>
          </div>

          <div className={styles.productActionsDesktop}>
            <Button
              className={styles.addBtn}
              onClick={handleAdd}
              disabled={!product.in_stock}
            >
              {added ? (
                <>
                  <IconCheck size={18} stroke={2} /> Добавлено
                </>
              ) : (
                <>В корзину · {formatMoney(lineTotal)} ₽</>
              )}
            </Button>
            <Button variant="secondary" onClick={() => navigate(`/store/${slug}/cart`)}>
              Корзина
            </Button>
          </div>
        </div>
      </main>

      <div className={styles.productDock}>
        <div className={styles.productDockInner}>
          <div className={styles.qtyStepperCompact}>
            <button
              type="button"
              className={styles.qtyBtn}
              onClick={() => bump(-1)}
              disabled={qty <= 1}
              aria-label="Меньше"
            >
              <IconMinus size={16} stroke={2} />
            </button>
            <span className={styles.qtyValueCompact}>{qty}</span>
            <button
              type="button"
              className={styles.qtyBtn}
              onClick={() => bump(1)}
              disabled={qty >= 999}
              aria-label="Больше"
            >
              <IconPlus size={16} stroke={2} />
            </button>
          </div>
          <Button className={styles.dockAdd} onClick={handleAdd} disabled={!product.in_stock}>
            {added ? 'Добавлено' : `${formatMoney(lineTotal)} ₽`}
          </Button>
        </div>
      </div>
    </div>
  )
}
