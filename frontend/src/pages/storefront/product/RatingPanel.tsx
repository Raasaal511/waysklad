import { StarRating } from '../../../shared/ui/StarRating'
import { Button } from '../../../shared/ui/Button'
import type { RatingDistribution } from '../../../entities/review/api'
import styles from './ReviewsSection.module.css'

interface RatingPanelProps {
  averageRating: number
  reviewsCount: number
  distribution: RatingDistribution
  ratingFilter: number | null
  onRatingFilterChange: (rating: number | null) => void
  onWriteReview: () => void
  writeButtonLabel: string | null
  writeButtonDisabled?: boolean
}

export function RatingPanel({
  averageRating,
  reviewsCount,
  distribution,
  ratingFilter,
  onRatingFilterChange,
  onWriteReview,
  writeButtonLabel,
  writeButtonDisabled,
}: RatingPanelProps) {
  const maxCount = Math.max(1, ...[5, 4, 3, 2, 1].map((n) => distribution[String(n) as '5' | '4' | '3' | '2' | '1']))

  return (
    <div className={styles.panel}>
      <p className={styles.panelLabel}>Рейтинг</p>
      <div className={styles.panelHeadline}>
        <StarRating value={averageRating} size={24} />
        <span>
          <span className={styles.panelScore}>{averageRating.toFixed(1)}</span>{' '}
          <span className={styles.panelScoreOf}>из 5</span>
        </span>
      </div>

      {[5, 4, 3, 2, 1].map((n) => {
        const count = distribution[String(n) as '5' | '4' | '3' | '2' | '1']
        const percent = reviewsCount > 0 ? (count / maxCount) * 100 : 0
        const active = ratingFilter === n
        return (
          <button
            key={n}
            type="button"
            className={active ? `${styles.histRow} ${styles.histRowActive}` : styles.histRow}
            onClick={() => onRatingFilterChange(active ? null : n)}
            aria-pressed={active}
          >
            <span className={styles.histStars}>{n} ★</span>
            <span className={styles.histBarTrack}>
              <span className={styles.histBarFill} style={{ width: `${percent}%` }} />
            </span>
            <span className={styles.histCount}>{count}</span>
          </button>
        )
      })}

      {writeButtonLabel ? (
        <Button className={styles.writeBtn} onClick={onWriteReview} disabled={writeButtonDisabled}>
          {writeButtonLabel}
        </Button>
      ) : null}
    </div>
  )
}
