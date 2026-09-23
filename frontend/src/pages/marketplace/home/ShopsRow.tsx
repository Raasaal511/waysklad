import { Link } from 'react-router-dom'
import { IconRosetteDiscountCheck } from '@tabler/icons-react'
import type { ShopChip } from '../../../entities/marketplace/api'
import { SectionHeader } from '../../../shared/ui/SectionHeader'
import styles from './ShopsRow.module.css'

function ShopCircle({ shop }: { shop: ShopChip }) {
  const hasReviews = shop.reviews_count > 0
  return (
    <Link to={`/store/${shop.slug}`} className={styles.item}>
      <span className={styles.circleWrap}>
        {shop.logo ? (
          <img src={shop.logo} alt="" width={104} height={104} className={styles.circle} loading="lazy" />
        ) : (
          <span className={styles.circleFallback} aria-hidden="true">
            {shop.name.charAt(0).toUpperCase()}
          </span>
        )}
        {shop.is_verified && (
          <IconRosetteDiscountCheck size={20} stroke={2} className={styles.verifiedBadge} aria-hidden="true" />
        )}
      </span>
      <span className={styles.name}>{shop.name}</span>
      {hasReviews && <span className={styles.rating}>★ {shop.average_rating.toFixed(1)}</span>}
    </Link>
  )
}

/** Ряд круглых логотипов магазинов — до 10 без скролла на десктопе, остальное скроллится. M-F3 п.1. */
export function ShopsRow({ shops }: { shops: ShopChip[] }) {
  if (shops.length === 0) return null
  return (
    <div>
      <SectionHeader title="Магазины" href="/marketplace/shops" linkLabel="Все магазины ›" />
      <div className={styles.row}>
        {shops.map((shop) => (
          <ShopCircle key={shop.slug} shop={shop} />
        ))}
      </div>
    </div>
  )
}

export function ShopsRowSkeleton() {
  return (
    <div>
      <div className={styles.skeletonHeader} aria-hidden="true" />
      <div className={styles.row} aria-hidden="true">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className={styles.item}>
            <span className={`${styles.circleWrap} ${styles.skeletonCircle}`} />
          </div>
        ))}
      </div>
    </div>
  )
}
