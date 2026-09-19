import { Link } from 'react-router-dom'
import type { StorefrontShopProfile } from '../../../entities/storefront/api'
import { formatMonthYearGenitive } from './productUtils'
import pageStyles from './ProductPage.module.css'
import styles from './ProductAside.module.css'

interface ShopCardProps {
  profile: StorefrontShopProfile
}

export function ShopCard({ profile }: ShopCardProps) {
  const hasReviews = profile.rating.reviews_count > 0

  return (
    <div className={pageStyles.card}>
      <Link to={`/store/${profile.slug}`} className={styles.shopHeader}>
        {profile.logo ? (
          <img src={profile.logo} alt={profile.name} className={styles.shopLogo} />
        ) : (
          <div className={styles.shopLogoFallback}>{profile.name.charAt(0).toUpperCase()}</div>
        )}
        <div style={{ minWidth: 0 }}>
          <p className={styles.shopName}>{profile.name}</p>
          {hasReviews ? (
            <p className={styles.shopRating}>
              <span className={styles.shopRatingStar}>★ {profile.rating.average_rating.toFixed(1)}</span>
              <span className={styles.shopRatingCount}>{profile.rating.reviews_count} отзыва</span>
            </p>
          ) : (
            <p className={styles.shopRating} style={{ color: 'var(--text-muted)' }}>
              Новый магазин
            </p>
          )}
          {profile.on_platform_since && (
            <p className={styles.shopSince}>На ВайСклад с {formatMonthYearGenitive(profile.on_platform_since)}</p>
          )}
        </div>
      </Link>

      <div className={styles.shopStats}>
        <div className={styles.shopStat}>
          <p className={styles.shopStatValue}>{profile.products_count}</p>
          <p className={styles.shopStatLabel}>товаров</p>
        </div>
        {profile.orders_count_label && (
          <div className={styles.shopStat}>
            <p className={styles.shopStatValue}>{profile.orders_count_label}</p>
            <p className={styles.shopStatLabel}>заказов</p>
          </div>
        )}
        {profile.min_order_total && (
          <div className={styles.shopStat}>
            <p className={styles.shopStatValue}>{profile.min_order_total} ₽</p>
            <p className={styles.shopStatLabel}>мин. заказ</p>
          </div>
        )}
      </div>
    </div>
  )
}
