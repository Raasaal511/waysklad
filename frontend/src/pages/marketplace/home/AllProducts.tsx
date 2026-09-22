import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listMarketplaceProducts, type MarketplaceProduct } from '../../../entities/marketplace/api'
import { SectionHeader } from '../../../shared/ui/SectionHeader'
import { ProductGrid } from '../../storefront/ProductGrid'

const PAGE_SIZE = 20

/** «Все товары» внизу главной — sort=popular, 20 штук; «Показать ещё» уводит в режим
 * каталога и прокручивает к сетке (M-F4 п.2). */
export function AllProducts() {
  const navigate = useNavigate()
  const [items, setItems] = useState<MarketplaceProduct[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    listMarketplaceProducts({ sort: 'popular', limit: PAGE_SIZE, offset: 0 })
      .then((data) => {
        if (!cancelled) setItems(data.products)
      })
      .catch(() => {
        if (!cancelled) setItems([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  function goToCatalog() {
    navigate('/marketplace?sort=popular')
  }

  return (
    <div>
      <SectionHeader title="Все товары" />
      <ProductGrid
        items={items}
        getHref={(item) => `/store/${item.shop_slug}/products/${item.id}`}
        showShop
        loading={loading}
        skeletonCount={PAGE_SIZE}
        onLoadMore={!loading && items.length > 0 ? goToCatalog : undefined}
        hasMore={!loading && items.length > 0}
      />
    </div>
  )
}
