import { useSearchParams } from 'react-router-dom'
import { MarketplaceCatalog } from './MarketplaceCatalog'
import { MarketplaceHome } from './home/MarketplaceHome'

/**
 * /marketplace — главная (без параметров) или каталог (есть q/pcat/section/фильтры).
 * Не подключён к роутеру, пока маркетплейс выключен (см. TASK_PUBLIC_UNIFY).
 * Фильтр по городу убран — вернём отдельно, когда решим модель.
 */
export function MarketplacePage() {
  const [searchParams] = useSearchParams()

  const isCatalogMode =
    searchParams.has('q') ||
    searchParams.has('pcat') ||
    searchParams.has('category') ||
    searchParams.has('section') ||
    searchParams.has('price_min') ||
    searchParams.has('price_max') ||
    searchParams.has('in_stock_only') ||
    searchParams.has('with_discount') ||
    searchParams.has('min_rating') ||
    searchParams.has('shop_slug') ||
    searchParams.has('sort')

  if (isCatalogMode) return <MarketplaceCatalog />
  return <MarketplaceHome />
}
