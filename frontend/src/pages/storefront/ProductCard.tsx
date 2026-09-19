import { Link } from 'react-router-dom'
import { IconPlus, IconHeart, IconHeartFilled } from '@tabler/icons-react'
import { formatMoney, formatQuantity } from '../../shared/lib/format'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import styles from './ProductCard.module.css'

export interface ProductCardItem {
  id: number
  name: string
  retail_price: string
  photo: string
  in_stock: boolean
  sold_count?: string
  average_rating?: number
  reviews_count?: number
  shop_name?: string
}

interface ProductCardProps {
  item: ProductCardItem
  href: string
  favorite?: boolean
  onToggleFavorite?: () => void
  onQuickAdd?: () => void
  showShopName?: boolean
}

/** Общая карточка товара — каталог магазина, похожие товары, маркетплейс, недавно просмотренные. */
export function ProductCard({ item, href, favorite, onToggleFavorite, onQuickAdd, showShopName }: ProductCardProps) {
  const hasRating = (item.reviews_count ?? 0) > 0
  const hasSold = Number(item.sold_count ?? 0) > 0

  return (
    <article className={styles.card}>
      <Link to={href} className={styles.link}>
        <div className={styles.photo}>
          <ProductPhoto src={item.photo} size={48} />
          {!item.in_stock && <span className={styles.outOfStock}>Нет в наличии</span>}
          {hasSold && <span className={styles.soldBadge}>Продано {formatQuantity(item.sold_count!)}</span>}
        </div>
        <div className={styles.body}>
          {showShopName && item.shop_name && <p className={styles.shopName}>{item.shop_name}</p>}
          <h3 className={styles.name}>{item.name}</h3>
          {hasRating && (
            <p className={styles.meta}>
              <span className={styles.metaStar}>★ {item.average_rating!.toFixed(1)}</span>
            </p>
          )}
          <div className={styles.footer}>
            <p className={styles.price}>{formatMoney(item.retail_price)} ₽</p>
            {item.in_stock && onQuickAdd && (
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
    </article>
  )
}
