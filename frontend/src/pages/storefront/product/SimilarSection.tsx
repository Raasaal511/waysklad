import { Link } from 'react-router-dom'
import { useSimilar } from './useProductPageData'
import { ProductGrid } from '../ProductGrid'
import pageStyles from './ProductPage.module.css'
import styles from './SimilarSection.module.css'

interface SimilarSectionProps {
  slug: string
  productId: string
  shopName: string
}

/**
 * «Ещё в магазине» — ленивая загрузка по IntersectionObserver.
 * Второй вариант секции (scope="marketplace", похожие товары в других
 * магазинах) убран вместе с маркетплейсом: backend отдаёт на него 404.
 * Сам API-контракт с обоими scope жив — см. entities/storefront/api.ts.
 */
export function SimilarSection({ slug, productId, shopName }: SimilarSectionProps) {
  const { setRef, data, loading } = useSimilar(slug, productId, 'shop')

  const shopItems = data?.shop_products ?? []

  if (data && shopItems.length === 0) {
    // пустой ответ после загрузки — секция не рендерится вообще
    return <div ref={setRef} />
  }

  return (
    <div className={pageStyles.card} ref={setRef}>
      <div className={styles.head}>
        <h2 className={styles.title}>Ещё в магазине «{shopName}»</h2>
        <Link to={`/store/${slug}`} className={styles.allLink}>
          Все товары ›
        </Link>
      </div>

      {loading && !data ? (
        <ProductGrid items={[]} getHref={() => ''} loading skeletonCount={5} />
      ) : (
        <ProductGrid items={shopItems} getHref={(item) => `/store/${slug}/products/${item.id}`} />
      )}
    </div>
  )
}
