import { useRef, useState } from 'react'
import type { HomeSection } from '../../../entities/marketplace/api'
import { SectionHeader } from '../../../shared/ui/SectionHeader'
import { ProductGrid } from '../../storefront/ProductGrid'

/** Секция товаров главной («Скидки», «Хиты продаж», …) — рендерит сетку только когда
 * попала в область видимости (IntersectionObserver, rootMargin 600px), до этого —
 * skeleton той же высоты, чтобы блоки ниже не прыгали. M-F3 п.3. */
export function ProductSection({ section }: { section: HomeSection }) {
  const [visible, setVisible] = useState(false)
  const observerRef = useRef<IntersectionObserver | null>(null)

  function setNode(node: HTMLDivElement | null) {
    observerRef.current?.disconnect()
    if (!node || visible) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin: '600px' },
    )
    observer.observe(node)
    observerRef.current = observer
  }

  // Мобильный: первая секция («Скидки») — сетка 2 колонки, 6 товаров; остальные —
  // горизонтальный скролл (M-F3 п.3). Десктоп показывает все до 10 (сетка 5 колонок,
  // 2 строки) для обеих — обрезка «Скидок» до 6 карточек сделана в CSS ProductGrid
  // (mobileLimitSix), не через slice(), чтобы не резать десктопную сетку.
  const isDiscount = section.key === 'discount'

  return (
    <div ref={setNode}>
      <SectionHeader title={section.title} href={`/marketplace?section=${section.key}`} />
      {visible ? (
        <ProductGrid
          items={section.products}
          getHref={(item) => `/store/${item.shop_slug}/products/${item.id}`}
          showShop
          mobileScroll={!isDiscount}
          mobileLimitSix={isDiscount}
        />
      ) : (
        <ProductGrid
          items={[]}
          getHref={() => ''}
          loading
          skeletonCount={section.products.length || 5}
          mobileScroll={!isDiscount}
          mobileLimitSix={isDiscount}
        />
      )}
    </div>
  )
}
