import { loadRecentlyViewed } from './recentlyViewed'
import { ProductGrid } from '../ProductGrid'
import pageStyles from './ProductPage.module.css'
import styles from './SimilarSection.module.css'

interface RecentlyViewedSectionProps {
  slug: string
  currentProductId: number
}

/** «Вы недавно смотрели» — из localStorage, без текущего товара, скрыта при < 2 товарах. */
export function RecentlyViewedSection({ slug, currentProductId }: RecentlyViewedSectionProps) {
  const items = loadRecentlyViewed(slug).filter((p) => p.id !== currentProductId)
  if (items.length < 2) return null

  return (
    <div className={pageStyles.card}>
      <div className={styles.head}>
        <h2 className={styles.title}>Вы недавно смотрели</h2>
      </div>
      <ProductGrid items={items} getHref={(item) => `/store/${slug}/products/${item.id}`} />
    </div>
  )
}
