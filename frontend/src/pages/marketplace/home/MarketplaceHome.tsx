import { EmptyState } from '../../../shared/ui/EmptyState'
import { AllProducts } from './AllProducts'
import { CategoryTiles, CategoryTilesSkeleton } from './CategoryTiles'
import { HeroCarousel, HeroCarouselSkeleton } from './HeroCarousel'
import styles from './MarketplaceHome.module.css'
import { ProductSection } from './ProductSection'
import { PromoTiles, PromoTilesSkeleton } from './PromoTiles'
import { SectionChips } from './SectionChips'
import { ShopsRow, ShopsRowSkeleton } from './ShopsRow'
import { useMarketplaceHome } from './useMarketplaceHome'

interface MarketplaceHomeProps {
  city: string | null
  onNearMe: () => void
}

/** Главная маркетплейса (режим без параметров в URL) — порядок блоков по M-F3 п.4. */
export function MarketplaceHome({ city, onNearMe }: MarketplaceHomeProps) {
  const { data, loading, error } = useMarketplaceHome(city)

  if (error) {
    return (
      <div className={styles.page}>
        <EmptyState
          title="Не удалось загрузить главную"
          description={error}
          actionLabel="Повторить"
          onAction={() => window.location.reload()}
        />
      </div>
    )
  }

  // Ни одного магазина на платформе (не только в выбранном городе) — общий empty-shelf.
  if (!loading && data && data.stats.shops_count === 0) {
    return (
      <div className={styles.page}>
        <EmptyState
          illustration="empty-shelf"
          title="Пока нет магазинов с открытой витриной"
          description="Загляните позже — продавцы уже подключаются к платформе"
        />
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <SectionChips onNearMe={onNearMe} />

      {loading || !data ? <HeroCarouselSkeleton /> : <HeroCarousel banners={data.banners.hero} city={city} />}

      {loading || !data ? <CategoryTilesSkeleton /> : <CategoryTiles categories={data.categories} />}

      {loading || !data ? <PromoTilesSkeleton /> : <PromoTiles promo={data.banners.promo} />}

      {loading || !data ? <ShopsRowSkeleton /> : <ShopsRow shops={data.shops} />}

      {!loading &&
        data &&
        data.sections.map((section) => <ProductSection key={section.key} section={section} />)}

      <AllProducts city={city} />

      {!loading && data && (
        <p className={styles.stats}>
          {data.stats.shops_count} магазинов · {data.stats.products_count} товаров ·{' '}
          {data.stats.cities_count} городов
        </p>
      )}
    </div>
  )
}
