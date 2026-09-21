import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { IconHeart, IconHeartFilled, IconPlus, IconShieldCheck } from '@tabler/icons-react'
import { formatMoney, formatPriceOrRequest, formatQuantity } from '../../shared/lib/format'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import styles from './ProductCard.module.css'

export interface ProductCardItem {
  id: number
  name: string
  retail_price: string
  old_price?: string | null
  discount_percent?: number | null
  photo: string
  in_stock: boolean
  is_new?: boolean
  is_hit?: boolean
  sold_count?: string
  average_rating?: number
  reviews_count?: number
  unit_label?: string | null
  shop_slug?: string
  shop_name?: string
  shop_is_verified?: boolean
}

interface ProductCardProps {
  item: ProductCardItem
  href: string
  /** Показывать строку магазина под названием (маркетплейс, похожие в других магазинах). */
  showShop?: boolean
  favorite?: boolean
  onToggleFavorite?: () => void
  onQuickAdd?: () => void
}

/** Общая карточка товара — каталог магазина, маркетплейс, похожие товары, недавно просмотренные, избранное. */
export function ProductCard({ item, href, showShop, favorite, onToggleFavorite, onQuickAdd }: ProductCardProps) {
  // подтверждение добавления в корзину: класс снимается по таймеру, поэтому
  // таймер чистится при размонтировании (карточка живёт в виртуальном списке)
  const [justAdded, setJustAdded] = useState(false)
  const addedTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => {
    if (addedTimer.current) clearTimeout(addedTimer.current)
  }, [])

  function flashAdded() {
    if (addedTimer.current) clearTimeout(addedTimer.current)
    setJustAdded(true)
    addedTimer.current = setTimeout(() => setJustAdded(false), 600)
  }

  const hasRating = (item.reviews_count ?? 0) > 0
  const hasSold = Number(item.sold_count ?? 0) > 0
  const hasOldPrice = item.old_price != null && Number(item.old_price) > Number(item.retail_price)

  // Приоритет бейджей по блоку «Д» п.6: нет в наличии → скидка → хит → новинка, не больше двух.
  const badges: { key: string; label: string; tone: 'out' | 'discount' | 'hit' | 'new' }[] = []
  if (!item.in_stock) badges.push({ key: 'out', label: 'Нет в наличии', tone: 'out' })
  if (item.discount_percent) badges.push({ key: 'discount', label: `−${item.discount_percent}%`, tone: 'discount' })
  if (item.is_hit) badges.push({ key: 'hit', label: 'Хит', tone: 'hit' })
  if (item.is_new) badges.push({ key: 'new', label: 'Новинка', tone: 'new' })
  const shownBadges = badges.slice(0, 2)

  return (
    <article className={styles.card}>
      <div className={styles.photo} data-dim={!item.in_stock || undefined}>
        {/* CSS растягивает фото/плейсхолдер на 100% контейнера (aspect-ratio 1/1) —
            size здесь влияет только на размер иконки-заглушки, не на сам контейнер. */}
        <ProductPhoto src={item.photo} size={96} />
        {shownBadges.length > 0 && (
          <div className={styles.badges}>
            {shownBadges.map((b) => (
              <span key={b.key} className={styles.badge} data-tone={b.tone}>
                {b.label}
              </span>
            ))}
          </div>
        )}
        {onToggleFavorite && (
          <button
            type="button"
            className={styles.favBtn}
            onClick={onToggleFavorite}
            aria-label={favorite ? 'Убрать из избранного' : 'В избранное'}
          >
            {favorite ? <IconHeartFilled size={18} /> : <IconHeart size={18} stroke={1.8} />}
          </button>
        )}
      </div>

      <div className={styles.body}>
        <h3 className={styles.name}>
          <Link to={href} className={styles.link}>
            {item.name}
          </Link>
        </h3>

        <div className={styles.priceRow}>
          <span className={styles.price}>{formatPriceOrRequest(item.retail_price)}</span>
          {hasOldPrice && <span className={styles.oldPrice}>{formatMoney(item.old_price!)} ₽</span>}
          {hasRating && <span className={styles.rating}>★ {item.average_rating!.toFixed(1)}</span>}
          {item.in_stock && onQuickAdd && (
            <button
              type="button"
              className={`${styles.quickAdd} ${justAdded ? styles.quickAddAdded : ''}`}
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                onQuickAdd()
                flashAdded()
              }}
              aria-label="Добавить в корзину"
            >
              <IconPlus size={18} stroke={2} />
            </button>
          )}
        </div>

        {showShop && item.shop_name && (
          <div className={styles.shopRow}>
            <Link
              to={`/store/${item.shop_slug}`}
              className={styles.shopName}
              onClick={(e) => e.stopPropagation()}
            >
              {item.shop_is_verified && <IconShieldCheck size={14} stroke={2} className={styles.shopVerified} />}
              <span className={styles.shopNameText}>{item.shop_name}</span>
            </Link>
            {hasSold && (
              <span className={styles.sold}>Продано {formatQuantity(item.sold_count!)}</span>
            )}
          </div>
        )}
      </div>
    </article>
  )
}

/** Skeleton той же геометрии, что ProductCard — для сетки в состоянии загрузки. */
export function ProductCardSkeleton() {
  return (
    <div className={styles.card} aria-hidden="true">
      <div className={`${styles.photo} ${styles.skeletonPhoto}`} />
      <div className={styles.body}>
        <div className={styles.skeletonLine} style={{ width: '100%' }} />
        <div className={styles.skeletonLine} style={{ width: '70%' }} />
        <div className={styles.skeletonLine} style={{ width: '40%', height: 18, marginTop: 4 }} />
      </div>
    </div>
  )
}
