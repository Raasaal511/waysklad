import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { IconCalendar, IconStar, IconArrowUp, IconArrowDown, IconRefresh } from '@tabler/icons-react'
import { useProductReviews } from './useProductPageData'
import { ReviewCard } from './ReviewCard'
import { RatingPanel } from './RatingPanel'
import { ReviewFormModal } from './ReviewFormModal'
import { Lightbox } from '../../../shared/ui/Lightbox'
import { loadCustomerToken } from '../../../entities/auth/customerApi'
import {
  voteReview,
  getReviewEligibility,
  type Review,
  type ReviewPhotoRef,
  type ReviewSort,
} from '../../../entities/review/api'
import pageStyles from './ProductPage.module.css'
import styles from './ReviewsSection.module.css'

interface ReviewsSectionProps {
  slug: string
  productId: string
  /** Отдаёт photos наверх для BuyerPhotos — чтобы не делать второй запрос отзывов
   *  только ради фото (не больше 4 запросов на странице товара, блок «Д» п.2 P7). */
  onPhotosLoaded?: (photos: ReviewPhotoRef[]) => void
}

const PAGE_SIZE = 10

export function ReviewsSection({ slug, productId, onPhotosLoaded }: ReviewsSectionProps) {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const sort = (searchParams.get('rsort') as ReviewSort) || 'date_desc'
  const withPhotos = searchParams.get('rphoto') === '1'
  const tag = searchParams.get('rtag') || undefined
  const ratingFilter = searchParams.get('rrating') ? Number(searchParams.get('rrating')) : null

  const { page, loading, loadingMore, error, loadMore, reload } = useProductReviews(slug, productId, {
    sort,
    with_photos: withPhotos || undefined,
    tag,
    rating: ratingFilter ?? undefined,
    limit: PAGE_SIZE,
  })

  useEffect(() => {
    if (page) onPhotosLoaded?.(page.photos)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page])

  const [isLoggedIn, setIsLoggedIn] = useState(() => !!loadCustomerToken())
  const [lightbox, setLightbox] = useState<{ photos: string[]; index: number; review: Review } | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [eligibility, setEligibility] = useState<{
    can_review: boolean
    request_id: number | null
    reason: 'ok' | 'no_purchase' | 'already_reviewed'
  } | null>(null)

  useEffect(() => {
    function sync() {
      setIsLoggedIn(!!loadCustomerToken())
    }
    window.addEventListener('waysklad:customer-auth', sync)
    return () => window.removeEventListener('waysklad:customer-auth', sync)
  }, [])

  useEffect(() => {
    if (!isLoggedIn) {
      setEligibility(null)
      return
    }
    let cancelled = false
    getReviewEligibility(slug, Number(productId))
      .then((e) => !cancelled && setEligibility(e))
      .catch(() => !cancelled && setEligibility(null))
    return () => {
      cancelled = true
    }
  }, [slug, productId, isLoggedIn])

  function patch(next: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams)
    for (const [k, v] of Object.entries(next)) {
      if (v == null) params.delete(k)
      else params.set(k, v)
    }
    setSearchParams(params, { replace: true })
  }

  function toggleSortField(field: 'date' | 'rating') {
    const isDate = field === 'date'
    const currentlyActive = isDate ? sort.startsWith('date') : sort.startsWith('rating')
    if (!currentlyActive) {
      patch({ rsort: isDate ? 'date_desc' : 'rating_desc' })
      return
    }
    const isDesc = sort.endsWith('desc')
    patch({ rsort: isDate ? (isDesc ? 'date_asc' : 'date_desc') : isDesc ? 'rating_asc' : 'rating_desc' })
  }

  // Голоса накладываются локально поверх списка из хука — оптимистичное обновление
  // без похода на сервер за всем списком заново; при ошибке откатываем конкретную запись.
  const [voteOverrides, setVoteOverrides] = useState<Record<number, { likes: number; dislikes: number; my_vote: 0 | 1 | -1 }>>({})

  async function handleVote(reviewId: number, value: 1 | -1 | 0) {
    if (!page) return
    const target = page.reviews.find((r) => r.id === reviewId)
    if (!target) return
    const current = voteOverrides[reviewId] ?? { likes: target.likes, dislikes: target.dislikes, my_vote: target.my_vote }
    let likes = current.likes
    let dislikes = current.dislikes
    if (current.my_vote === 1) likes -= 1
    if (current.my_vote === -1) dislikes -= 1
    if (value === 1) likes += 1
    if (value === -1) dislikes += 1

    setVoteOverrides((prev) => ({ ...prev, [reviewId]: { likes, dislikes, my_vote: value } }))

    try {
      const result = await voteReview(reviewId, value)
      setVoteOverrides((prev) => ({ ...prev, [reviewId]: result }))
    } catch {
      setVoteOverrides((prev) => ({ ...prev, [reviewId]: current }))
    }
  }

  function handleWriteReview() {
    if (!isLoggedIn) {
      const next = encodeURIComponent(
        `/store/${slug}/products/${productId}?writeReview=1#reviews`,
      )
      navigate(`/store/${slug}/login?next=${next}`)
      return
    }
    setShowForm(true)
  }

  useEffect(() => {
    if (!isLoggedIn) return
    if (searchParams.get('writeReview') !== '1') return
    if (!eligibility?.can_review) return
    setShowForm(true)
    const params = new URLSearchParams(searchParams)
    params.delete('writeReview')
    setSearchParams(params, { replace: true })
  }, [isLoggedIn, eligibility, searchParams, setSearchParams])

  if (error && !page) {
    return (
      <section className={pageStyles.card} id="reviews">
        <div className={styles.errorBox}>
          <p>Не удалось загрузить отзывы</p>
          <button type="button" className={styles.showMoreBtn} onClick={reload}>
            <IconRefresh size={14} stroke={1.8} style={{ marginRight: 6 }} />
            Повторить
          </button>
        </div>
      </section>
    )
  }

  const reviewsCount = page?.reviews_count ?? 0
  const total = page?.total ?? 0

  let writeButtonLabel: string | null = 'Написать отзыв'
  let writeButtonDisabled = false
  let eligibilityHint: string | null = null
  if (isLoggedIn && eligibility) {
    if (eligibility.reason === 'no_purchase') {
      writeButtonLabel = null
      eligibilityHint = 'Отзыв можно оставить после покупки в этом магазине'
    } else if (eligibility.reason === 'already_reviewed') {
      writeButtonLabel = null
      eligibilityHint = 'Вы уже оставили отзыв'
    }
  }

  return (
    <section className={pageStyles.card} id="reviews">
      <h2 className={styles.headTitle}>
        Отзывы {reviewsCount > 0 && <span className={styles.headCount}>{reviewsCount}</span>}
      </h2>

      <div className={styles.layout} style={{ marginTop: 16 }}>
        <div className={reviewsCount === 0 ? `${styles.list} ${styles.listEmpty}` : styles.list}>
          {page && page.photos.length > 0 && (
            <div className={styles.photoStrip}>
              {page.photos.map((p, i) => (
                <button
                  key={`${p.url}-${i}`}
                  type="button"
                  className={styles.photoTile}
                  onClick={() => {
                    const review = page.reviews.find((r) => r.id === p.review_id)
                    setLightbox({
                      photos: page.photos.map((ph) => ph.url),
                      index: i,
                      review: review ?? ({ id: p.review_id } as Review),
                    })
                  }}
                  aria-label="Открыть фото"
                >
                  <img src={p.url} alt="" />
                </button>
              ))}
            </div>
          )}

          {reviewsCount > 0 && (
            <div className={styles.controls}>
              <span className={styles.sortLabel}>Сортировать по:</span>
              <button
                type="button"
                className={sort.startsWith('date') ? `${styles.sortBtn} ${styles.sortBtnActive}` : styles.sortBtn}
                onClick={() => toggleSortField('date')}
              >
                <IconCalendar size={14} stroke={1.8} />
                Дата
                {sort.startsWith('date') &&
                  (sort.endsWith('desc') ? <IconArrowDown size={12} stroke={2} /> : <IconArrowUp size={12} stroke={2} />)}
              </button>
              <button
                type="button"
                className={sort.startsWith('rating') ? `${styles.sortBtn} ${styles.sortBtnActive}` : styles.sortBtn}
                onClick={() => toggleSortField('rating')}
              >
                <IconStar size={14} stroke={1.8} />
                Оценка
                {sort.startsWith('rating') &&
                  (sort.endsWith('desc') ? <IconArrowDown size={12} stroke={2} /> : <IconArrowUp size={12} stroke={2} />)}
              </button>
              {(page?.with_photos_count ?? 0) > 0 && (
                <label className={styles.photoCheck}>
                  <input
                    type="checkbox"
                    checked={withPhotos}
                    onChange={(e) => patch({ rphoto: e.target.checked ? '1' : null })}
                  />
                  Только с фото {page?.with_photos_count}
                </label>
              )}
            </div>
          )}

          {page && page.tags.length > 0 && (
            <div className={styles.tagsRow}>
              {page.tags.map((t) => (
                <button
                  key={t.code}
                  type="button"
                  className={tag === t.code ? `${styles.tagChip} ${styles.tagChipActive}` : styles.tagChip}
                  onClick={() => patch({ rtag: tag === t.code ? null : t.code })}
                >
                  {t.label} ({t.count})
                </button>
              ))}
            </div>
          )}

          {loading && !page ? (
            <p style={{ color: 'var(--text-muted)' }}>Загрузка отзывов…</p>
          ) : reviewsCount === 0 ? (
            <div className={styles.empty}>
              <img src="/illustrations/empty-reviews.png" alt="" />
              <p>Пока нет отзывов</p>
              {writeButtonLabel && (
                <button type="button" className={styles.showMoreBtn} onClick={handleWriteReview} disabled={writeButtonDisabled}>
                  {writeButtonLabel}
                </button>
              )}
              {eligibilityHint && <p>{eligibilityHint}</p>}
            </div>
          ) : (page?.reviews.length ?? 0) === 0 ? (
            <p style={{ color: 'var(--text-muted)' }}>Нет отзывов с такими фильтрами</p>
          ) : (
            <>
              {page!.reviews.map((r) => {
                const override = voteOverrides[r.id]
                const review = override ? { ...r, ...override } : r
                return (
                  <ReviewCard
                    key={r.id}
                    id={`review-${r.id}`}
                    review={review}
                    isOwn={false}
                    onVote={handleVote}
                    onOpenPhoto={(photos, index, rv) => setLightbox({ photos, index, review: rv })}
                    onRequireLogin={() => {
                      const next = encodeURIComponent(
                        `/store/${slug}/products/${productId}#review-${r.id}`,
                      )
                      navigate(`/store/${slug}/login?next=${next}`)
                    }}
                    isLoggedIn={isLoggedIn}
                  />
                )
              })}
              {page!.reviews.length < total && (
                <button type="button" className={styles.showMoreBtn} onClick={loadMore} disabled={loadingMore}>
                  {loadingMore ? 'Загрузка…' : 'Показать ещё'}
                </button>
              )}
            </>
          )}
        </div>

        {page && reviewsCount > 0 && (
          <RatingPanel
            averageRating={page.average_rating}
            reviewsCount={page.reviews_count}
            distribution={page.rating_distribution}
            ratingFilter={ratingFilter}
            onRatingFilterChange={(r) => patch({ rrating: r != null ? String(r) : null })}
            onWriteReview={handleWriteReview}
            writeButtonLabel={writeButtonLabel}
            writeButtonDisabled={writeButtonDisabled}
          />
        )}
      </div>

      {eligibilityHint && reviewsCount > 0 && <p className={styles.eligibilityHint}>{eligibilityHint}</p>}

      {lightbox && (
        <Lightbox
          photos={lightbox.photos}
          index={lightbox.index}
          onIndexChange={(i) => setLightbox((prev) => (prev ? { ...prev, index: i } : prev))}
          onClose={() => setLightbox(null)}
          captions={lightbox.photos.map(() => ({
            authorName: lightbox.review.author_name,
            rating: lightbox.review.rating,
            text: lightbox.review.text?.slice(0, 120),
            reviewAnchor: `#review-${lightbox.review.id}`,
          }))}
        />
      )}

      {showForm && eligibility?.can_review && eligibility.request_id != null && (
        <ReviewFormModal
          requestId={eligibility.request_id}
          productId={Number(productId)}
          onClose={() => setShowForm(false)}
          onSuccess={() => {
            setShowForm(false)
            reload()
            getReviewEligibility(slug, Number(productId))
              .then(setEligibility)
              .catch(() => {})
          }}
        />
      )}
    </section>
  )
}
