import { Button } from '../../shared/ui/Button'
import { ProductCard, ProductCardSkeleton, type ProductCardItem } from './ProductCard'
import styles from './ProductGrid.module.css'

interface ProductGridProps<T extends ProductCardItem> {
  items: T[]
  getHref: (item: T) => string
  showShop?: boolean
  favorites?: number[]
  onToggleFavorite?: (item: T) => void
  onQuickAdd?: (item: T) => void
  /** Режим загрузки — рисует count скелетонов вместо items. */
  loading?: boolean
  skeletonCount?: number
  /** «Показать ещё»: присутствие onLoadMore включает кнопку. */
  onLoadMore?: () => void
  loadingMore?: boolean
  hasMore?: boolean
}

/** Общая сетка карточек товара — каталог магазина, маркетплейс, избранное. Блок «Д» п.2. */
export function ProductGrid<T extends ProductCardItem>({
  items,
  getHref,
  showShop,
  favorites,
  onToggleFavorite,
  onQuickAdd,
  loading,
  skeletonCount = 10,
  onLoadMore,
  loadingMore,
  hasMore,
}: ProductGridProps<T>) {
  if (loading) {
    return (
      <div className={styles.grid}>
        {Array.from({ length: skeletonCount }).map((_, i) => (
          <ProductCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  return (
    <>
      <div className={styles.grid}>
        {items.map((item) => (
          <ProductCard
            // товары маркетплейса не уникальны по одному id (тот же id у разных
            // магазинов) — добавляем shop_slug к ключу, когда он есть
            key={item.shop_slug ? `${item.shop_slug}-${item.id}` : item.id}
            item={item}
            href={getHref(item)}
            showShop={showShop}
            favorite={favorites?.includes(item.id)}
            onToggleFavorite={onToggleFavorite ? () => onToggleFavorite(item) : undefined}
            onQuickAdd={onQuickAdd ? () => onQuickAdd(item) : undefined}
          />
        ))}
      </div>
      {onLoadMore && hasMore && (
        <div className={styles.loadMoreRow}>
          <Button variant="secondary" onClick={onLoadMore} disabled={loadingMore}>
            {loadingMore ? 'Загрузка…' : 'Показать ещё'}
          </Button>
        </div>
      )}
    </>
  )
}
