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
  /** На мобильном — горизонтальный скролл карточек 160px вместо сетки (секции главной
   * маркетплейса, кроме первой). На ≥768 поведение не меняется. M-F3 п.3. */
  mobileScroll?: boolean
  /** На мобильном показывать не больше 6 карточек сетки (секция «Скидки» главной —
   * 6 из до 10 загруженных, чтобы не резать десктопную сетку 5×2). На ≥768 не действует. */
  mobileLimitSix?: boolean
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
  mobileScroll,
  mobileLimitSix,
}: ProductGridProps<T>) {
  const gridClass = [
    styles.grid,
    mobileScroll ? styles.mobileScroll : '',
    mobileLimitSix ? styles.mobileLimitSix : '',
  ]
    .filter(Boolean)
    .join(' ')

  if (loading) {
    return (
      <div className={gridClass}>
        {Array.from({ length: skeletonCount }).map((_, i) => (
          <ProductCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  return (
    <>
      <div className={gridClass}>
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
