import { useParams, useSearchParams } from 'react-router-dom'
import { IconHeart, IconHeartFilled } from '@tabler/icons-react'
import { useState, useEffect, useRef, Suspense, lazy } from 'react'
import { FAVORITES_EVENT, loadFavorites, toggleFavorite } from '../../shared/lib/favorites'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { formatMoney, plural } from '../../shared/lib/format'
import {
  useStorefrontProduct,
  useShopProfile,
  useTrackProductView,
} from './product/useProductPageData'
import type { ReviewPhotoRef } from '../../entities/review/api'
import { ProductLayout } from './product/ProductLayout'
import { Breadcrumbs } from '../../shared/ui/Breadcrumbs'
import { ProductHeader } from './product/ProductHeader'
import { ProductGallery } from './product/ProductGallery'
import { BuyerPhotos } from './product/BuyerPhotos'
import { VariantList, variantListSectionTitle } from './product/VariantList'
import { MinOrderProgress } from './product/MinOrderProgress'
import { TotalCard } from './product/TotalCard'
import { ConditionsCard } from './product/ConditionsCard'
import { ShopCard } from './product/ShopCard'
import { FaqLinks } from './product/FaqLinks'
import { AboutSection } from './product/AboutSection'
import { WarrantySection } from './product/WarrantySection'
import { MobileDock } from './product/MobileDock'
import { ProductPageSkeleton, ProductPageError } from './product/ProductPageStates'
import { useSelection } from './product/useSelection'
import { variantPrice, galleryForVariant, buildProductBreadcrumbs } from './product/productUtils'
import { pushRecentlyViewed } from './product/recentlyViewed'
import { addToCart, loadCart } from './cart'
import { initialOrderQty } from '../../entities/storefront/api'
import shellStyles from './Storefront.module.css'
import styles from './product/ProductPage.module.css'

const ReviewsSection = lazy(() => import('./product/ReviewsSection').then((m) => ({ default: m.ReviewsSection })))
const SimilarSection = lazy(() => import('./product/SimilarSection').then((m) => ({ default: m.SimilarSection })))
const RecentlyViewedSection = lazy(() =>
  import('./product/RecentlyViewedSection').then((m) => ({ default: m.RecentlyViewedSection })),
)

// Окно защиты от двойного клика по «В корзину» — короче анимации «Добавлено» (1600ms),
// чтобы не мешать намеренным быстрым повторным добавлениям, но перекрыть double-click.
const ADD_GUARD_MS = 500

export function StorefrontProductPage() {
  const { slug = '', productId = '' } = useParams<{ slug: string; productId: string }>()
  const [searchParams] = useSearchParams()
  const highlightVariantId = searchParams.get('v')
  const { product, shopName, loading, error, errorStatus } = useStorefrontProduct(slug, productId)
  const [cartItems, setCartItems] = useState(() => loadCart(slug))
  const [favorites, setFavorites] = useState(() => loadFavorites(slug))
  const { selection, setQty, clear, totalQty, linesCount } = useSelection()
  const [added, setAdded] = useState(false)
  const [activePhoto, setActivePhoto] = useState(0)
  const [toast, setToast] = useState<string | null>(null)
  const [flashVariantKey, setFlashVariantKey] = useState<number | 'base' | null>(null)
  const lastAddAt = useRef(0)
  const [reviewPhotos, setReviewPhotos] = useState<ReviewPhotoRef[]>([])
  const { profile: shopProfile } = useShopProfile(slug)
  const [dockVisible, setDockVisible] = useState(false)

  useTrackProductView(slug, productId, !loading && !!product)

  // переход между товарами: скролл вверх, сброс выбора и фото
  useEffect(() => {
    if (!product) return
    window.scrollTo({ top: 0 })
    setActivePhoto(0)
    clear()
    // если в URL указан конкретный вариант — сразу выделяем его фото в галерее
    if (highlightVariantId) {
      const idx = product.variants.findIndex((v) => String(v.id) === highlightVariantId)
      if (idx >= 0 && product.variants[idx].photo) setActivePhoto(0)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product?.id])

  useEffect(() => {
    if (!product) return
    pushRecentlyViewed(slug, {
      id: product.id,
      name: product.name,
      retail_price: product.retail_price,
      old_price: product.old_price,
      discount_percent: product.discount_percent,
      photo: product.photo,
      in_stock: product.in_stock,
      average_rating: product.average_rating,
      reviews_count: product.reviews_count,
    })
  }, [slug, product])

  // JSON-LD schema.org Product — добавляется в useEffect, удаляется при уходе со страницы
  useEffect(() => {
    if (!product) return
    const script = document.createElement('script')
    script.type = 'application/ld+json'
    const jsonLd: Record<string, unknown> = {
      '@context': 'https://schema.org',
      '@type': 'Product',
      name: product.name,
      image: product.storefront_photos.length > 0 ? product.storefront_photos : product.photo ? [product.photo] : undefined,
      description: product.description || undefined,
      sku: product.sku || undefined,
      offers: {
        '@type': 'Offer',
        price: product.retail_price,
        priceCurrency: 'RUB',
        availability: product.in_stock ? 'https://schema.org/InStock' : 'https://schema.org/OutOfStock',
      },
    }
    if (product.reviews_count > 0) {
      jsonLd.aggregateRating = {
        '@type': 'AggregateRating',
        ratingValue: product.average_rating,
        reviewCount: product.reviews_count,
      }
    }
    script.textContent = JSON.stringify(jsonLd)
    document.head.appendChild(script)
    return () => {
      document.head.removeChild(script)
    }
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

  // мобильный dock появляется, когда TotalCard уходит из вьюпорта
  useEffect(() => {
    let observer: IntersectionObserver | null = null
    // TotalCard рендерится асинхронно (после первой загрузки товара) — небольшая отсрочка
    const timer = window.setTimeout(() => {
      const el = document.getElementById('product-total-card')
      if (!el) return
      observer = new IntersectionObserver(([entry]) => setDockVisible(!entry.isIntersecting), {
        rootMargin: '-56px 0px 0px 0px',
      })
      observer.observe(el)
    }, 0)
    return () => {
      window.clearTimeout(timer)
      observer?.disconnect()
    }
  }, [product])

  // избранное меняется и вне карточки — на /favorites и в другой вкладке
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

  function handleToggleFavorite() {
    if (!product) return
    setFavorites(toggleFavorite(slug, product.id))
  }

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.container}>
          <ProductPageSkeleton />
        </div>
      </div>
    )
  }

  if (error || !product) {
    return (
      <div className={styles.page}>
        <div className={styles.container}>
          <ProductPageError status={errorStatus} slug={slug} />
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

  const cartTotalInShop = cartItems.reduce((sum, i) => sum + Number(i.retail_price) * Number(i.quantity), 0)
  const cartQtyForThisProduct = cartItems
    .filter((i) => i.product_id === product.id)
    .reduce((sum, i) => sum + Number(i.quantity), 0)

  function handleAdd() {
    if (!product || !product.in_stock) return
    // Двойной клик по «В корзину» успевает сработать дважды до того, как React
    // перерисует кнопку с новым состоянием added — блокируем повторный вызов
    // коротким окном, независимым от рендера (P6, «мелочи»).
    const now = Date.now()
    if (now - lastAddAt.current < ADD_GUARD_MS) return
    lastAddAt.current = now
    if (selection.size === 0) {
      // ничего не выбрано: кнопка «В корзину» остаётся активной и сама добавляет
      // минимальное количество (п.6 промпта P4) — для товара без вариантов сразу
      // кладёт его в корзину, для товара с вариантами берёт первый доступный
      // и подсвечивает его в списке, чтобы покупатель видел, что именно добавлено
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
        const qty = initialOrderQty(product.min_order_qty, product.order_step_qty)
        addToCart(slug, {
          product_id: product.id,
          name: product.name,
          retail_price: variantPrice(product, firstAvailable),
          photo: firstAvailable.photo || product.photo,
          quantity: String(qty),
          variant_id: firstAvailable.id,
          variant_label: firstAvailable.display_name,
        })
        setCartItems(loadCart(slug))
        setAdded(true)
        setToast(`Добавлено: ${firstAvailable.display_name}`)
        setFlashVariantKey(firstAvailable.id)
        setTimeout(() => setAdded(false), 1600)
        setTimeout(() => setFlashVariantKey(null), 1700)
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
      <div className={styles.container}>
        <div className={shellStyles.crumbRow}>
          <Breadcrumbs items={buildProductBreadcrumbs(slug, product.category, product.name)} />
          <button
            type="button"
            className={shellStyles.iconGhost}
            onClick={handleToggleFavorite}
            aria-label={isFavorite ? 'Убрать из избранного' : 'В избранное'}
          >
            {isFavorite ? <IconHeartFilled size={20} /> : <IconHeart size={20} stroke={1.8} />}
          </button>
        </div>

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
                <h2 className={styles.blockTitle}>{variantListSectionTitle(product.variants.length)}</h2>
                <VariantList
                  product={product}
                  selection={selection}
                  onQtyChange={setQty}
                  onShowToast={setToast}
                  flashKey={flashVariantKey}
                />
              </div>
            </>
          }
          aside={
            <>
              {shopProfile?.min_order_total && (
                <MinOrderProgress
                  minOrderTotal={shopProfile.min_order_total}
                  currentTotal={cartTotalInShop + selectionTotal}
                />
              )}
              <TotalCard
                slug={slug}
                total={selectionTotal}
                linesCount={linesCount}
                totalQty={totalQty}
                inStock={product.in_stock}
                added={added}
                onAdd={handleAdd}
                cartQtyInShop={cartQtyForThisProduct}
                contacts={shopProfile?.contacts}
                productName={product.name}
              />
              {shopProfile && (
                <ConditionsCard addresses={shopProfile.addresses} paymentPolicy={shopProfile.policies.payment} />
              )}
              {shopProfile && <ShopCard profile={shopProfile} />}
              {shopProfile && <FaqLinks policies={shopProfile.policies} />}
            </>
          }
          below={
            <>
              <BuyerPhotos photos={reviewPhotos} />
              <AboutSection product={product} />
              <WarrantySection warrantyText={product.warranty_text} />
              <Suspense fallback={null}>
                {/* только товары этого же магазина: межмагазинный блок (scope="marketplace")
                    убран вместе с маркетплейсом — backend отдаёт на него 404 */}
                <SimilarSection slug={slug} productId={productId} shopName={shopName} />
              </Suspense>
              <Suspense fallback={null}>
                <ReviewsSection slug={slug} productId={productId} onPhotosLoaded={setReviewPhotos} />
              </Suspense>
              <Suspense fallback={null}>
                <RecentlyViewedSection slug={slug} currentProductId={product.id} />
              </Suspense>
            </>
          }
        />
      </div>

      {toast && (
        <div className={styles.toast} role="status">
          {toast}
        </div>
      )}

      {dockVisible && (
        <MobileDock
          total={selectionTotal}
          hasSelection={linesCount > 0}
          inStock={product.in_stock}
          added={added}
          onAdd={handleAdd}
          hasContacts={!!(shopProfile?.contacts && (shopProfile.contacts.phone || shopProfile.contacts.whatsapp || shopProfile.contacts.telegram))}
        />
      )}
    </div>
  )
}
