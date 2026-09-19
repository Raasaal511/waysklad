import { Link } from 'react-router-dom'
import { useSimilar } from './useProductPageData'
import { ProductCard } from '../ProductCard'
import pageStyles from './ProductPage.module.css'
import styles from './SimilarSection.module.css'

interface SimilarSectionProps {
  slug: string
  productId: string
  scope: 'shop' | 'marketplace'
  shopName: string
}

/** «Ещё в магазине» / «Похожие товары в других магазинах» — ленивая загрузка по IntersectionObserver. */
export function SimilarSection({ slug, productId, scope, shopName }: SimilarSectionProps) {
  const { setRef, data, loading } = useSimilar(slug, productId, scope)

  const shopItems = data?.shop_products ?? []
  const marketplaceItems = data?.marketplace_products ?? []
  const isEmpty = data && (scope === 'shop' ? shopItems.length === 0 : marketplaceItems.length === 0)
  const title = scope === 'shop' ? `Ещё в магазине «${shopName}»` : 'Похожие товары в других магазинах'

  if (isEmpty) {
    // пустой ответ после загрузки — секция не рендерится вообще
    return <div ref={setRef} />
  }

  return (
    <div className={pageStyles.card} ref={setRef}>
      <div className={styles.head}>
        <h2 className={styles.title}>{title}</h2>
        {scope === 'shop' && (
          <Link to={`/store/${slug}`} className={styles.allLink}>
            Все товары ›
          </Link>
        )}
      </div>

      {loading && !data ? (
        <div className={styles.skeletonGrid}>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className={styles.skeletonCard} />
          ))}
        </div>
      ) : (
        <div className={styles.grid}>
          {scope === 'shop'
            ? shopItems.map((item) => (
                <ProductCard key={item.id} item={item} href={`/store/${slug}/products/${item.id}`} />
              ))
            : marketplaceItems.map((item) => (
                <ProductCard
                  key={item.id}
                  item={item}
                  href={`/store/${item.shop_slug}/products/${item.id}`}
                  showShopName
                />
              ))}
        </div>
      )}
    </div>
  )
}
