import { Link } from 'react-router-dom'
import {
  IconBabyCarriage,
  IconBuildingWarehouse,
  IconCar,
  IconCategory,
  IconDeviceLaptop,
  IconHanger,
  IconHome,
  IconShoppingBag,
  IconSparkles,
  IconTools,
  type Icon,
  type IconProps,
} from '@tabler/icons-react'
import type { PlatformCategory } from '../../../entities/marketplace/api'
import styles from './CategoryTiles.module.css'

// Справочник платформенных категорий (docs/MARKETPLACE_HOME_PROMPTS.md, M-B1 §1) не
// отдаёт свою иконку — только картинку (может быть пустой). Заглушка по slug — на фронте.
const CATEGORY_ICONS: Record<string, (props: IconProps) => ReturnType<Icon>> = {
  electronics: IconDeviceLaptop,
  clothing: IconHanger,
  shoes: IconShoppingBag,
  tools: IconTools,
  auto: IconCar,
  accessories: IconShoppingBag,
  groceries: IconShoppingBag,
  products: IconShoppingBag,
  home: IconHome,
  beauty: IconSparkles,
  kids: IconBabyCarriage,
  construction: IconBuildingWarehouse,
}

const MAX_TILES = 6

export function CategoryTiles({ categories }: { categories: PlatformCategory[] }) {
  if (categories.length === 0) return null
  const visible = categories.slice(0, MAX_TILES)
  const hasMore = categories.length > MAX_TILES

  return (
    <div className={styles.grid}>
      {visible.map((cat) => {
        const Icon = CATEGORY_ICONS[cat.slug] ?? IconCategory
        return (
          <Link key={cat.id} to={`/marketplace?pcat=${cat.slug}`} className={styles.tile}>
            <span className={styles.name}>{cat.name}</span>
            <span className={styles.imageWrap}>
              {cat.image ? (
                <img src={cat.image} alt="" width={96} height={96} loading="lazy" />
              ) : (
                <Icon size={64} stroke={1.5} className={styles.fallbackIcon} />
              )}
            </span>
          </Link>
        )
      })}
      {hasMore && (
        // Спецификация просит мега-меню — отдельный новый UI-паттерн, не входящий в
        // объём этого шага (см. отчёт P5); ведём в каталог со всеми товарами, где
        // список категорий платформы доступен в панели фильтров целиком.
        <Link to="/marketplace?sort=popular" className={`${styles.tile} ${styles.moreTile}`}>
          <span className={styles.name}>Все категории ›</span>
        </Link>
      )}
    </div>
  )
}

export function CategoryTilesSkeleton() {
  return (
    <div className={styles.grid} aria-hidden="true">
      {Array.from({ length: MAX_TILES }).map((_, i) => (
        <div key={i} className={`${styles.tile} ${styles.skeletonTile}`} />
      ))}
    </div>
  )
}
