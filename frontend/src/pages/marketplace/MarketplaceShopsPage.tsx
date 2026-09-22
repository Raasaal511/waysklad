import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { IconRosetteDiscountCheck, IconSearch } from '@tabler/icons-react'
import { listMarketplaceShops, type ShopChip } from '../../entities/marketplace/api'
import { plural } from '../../shared/lib/format'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { Button } from '../../shared/ui/Button'
import { EmptyState } from '../../shared/ui/EmptyState'
import styles from './MarketplaceShopsPage.module.css'

const PAGE_SIZE = 20

function ShopCard({ shop }: { shop: ShopChip }) {
  const hasReviews = shop.reviews_count > 0
  return (
    <Link to={`/store/${shop.slug}`} className={styles.card}>
      <span className={styles.logoWrap}>
        {shop.logo ? (
          <img src={shop.logo} alt="" width={72} height={72} className={styles.logo} loading="lazy" />
        ) : (
          <span className={styles.logoFallback} aria-hidden="true">
            {shop.name.charAt(0).toUpperCase()}
          </span>
        )}
      </span>
      <span className={styles.name}>
        {shop.name}
        {shop.is_verified && <IconRosetteDiscountCheck size={16} stroke={2} className={styles.verified} />}
      </span>
      <span className={styles.meta}>
        {hasReviews ? `★ ${shop.average_rating.toFixed(1)} · ${shop.reviews_count} ${plural(shop.reviews_count, ['отзыв', 'отзыва', 'отзывов'])}` : 'Новый магазин'}
      </span>
      <span className={styles.meta}>
        {shop.products_count} {plural(shop.products_count, ['товар', 'товара', 'товаров'])}
      </span>
      <Button variant="secondary" className={styles.cardBtn}>
        В магазин
      </Button>
    </Link>
  )
}

/** /marketplace/shops — «Все магазины» (M-F4 §3), нужна как назначение ссылки «Все магазины ›»
 * из ряда магазинов главной (M-F3 §1), поэтому сделана в этом шаге минимально: поиск,
 * сортировка, сетка карточек, «Показать ещё». */
export function MarketplaceShopsPage() {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [sort, setSort] = useState<'popular' | 'rating' | 'new'>('popular')
  const [shops, setShops] = useState<ShopChip[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    setPageMeta({ title: 'Все магазины — ВайСклад', description: 'Магазины с открытой витриной на платформе ВайСклад' })
    return () => resetPageMeta()
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    listMarketplaceShops({ query: debouncedQuery || undefined, sort, limit: PAGE_SIZE, offset: 0 })
      .then((data) => {
        if (!cancelled) {
          setShops(data.shops)
          setTotal(data.total)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setShops([])
          setTotal(0)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [debouncedQuery, sort])

  async function loadMore() {
    if (loadingMore || shops.length >= total) return
    setLoadingMore(true)
    try {
      const data = await listMarketplaceShops({
        query: debouncedQuery || undefined,
        sort,
        limit: PAGE_SIZE,
        offset: shops.length,
      })
      setShops((prev) => [...prev, ...data.shops])
      setTotal(data.total)
    } catch {
      /* «Показать ещё» — не критично при сбое сети */
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Магазины</h1>

      <div className={styles.toolbar}>
        <label className={styles.search}>
          <IconSearch size={18} stroke={1.8} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Найти магазин…" />
        </label>
        <div className={styles.sortRow}>
          {(
            [
              { value: 'popular', label: 'Популярные' },
              { value: 'rating', label: 'По рейтингу' },
              { value: 'new', label: 'Новые' },
            ] as const
          ).map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={sort === opt.value ? `${styles.sortBtn} ${styles.sortBtnActive}` : styles.sortBtn}
              onClick={() => setSort(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className={styles.grid}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className={`${styles.card} ${styles.skeletonCard}`} aria-hidden="true" />
          ))}
        </div>
      ) : shops.length === 0 ? (
        <EmptyState
          illustration="empty-shelf"
          title={debouncedQuery ? 'Ничего не найдено' : 'Пока нет магазинов'}
          description={debouncedQuery ? 'Попробуйте изменить запрос' : undefined}
        />
      ) : (
        <>
          <div className={styles.grid}>
            {shops.map((shop) => (
              <ShopCard key={shop.slug} shop={shop} />
            ))}
          </div>
          {shops.length < total && (
            <div className={styles.loadMoreRow}>
              <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? 'Загрузка…' : 'Показать ещё'}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
