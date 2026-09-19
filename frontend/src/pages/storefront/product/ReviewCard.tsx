import { useState } from 'react'
import { IconThumbUp, IconThumbDown } from '@tabler/icons-react'
import type { Review } from '../../../entities/review/api'
import { StarRating } from '../../../shared/ui/StarRating'
import { relativeDate } from './productUtils'
import styles from './ReviewsSection.module.css'

interface ReviewCardProps {
  review: Review
  isOwn: boolean
  onVote: (reviewId: number, value: 1 | -1 | 0) => void
  onOpenPhoto: (photos: string[], index: number, review: Review) => void
  onRequireLogin: () => void
  isLoggedIn: boolean
  id?: string
}

export function ReviewCard({ review, isOwn, onVote, onOpenPhoto, onRequireLogin, isLoggedIn, id }: ReviewCardProps) {
  const [expanded, setExpanded] = useState(false)
  const authorLetter = review.author_name?.trim().charAt(0).toUpperCase() || '?'

  function handleVote(value: 1 | -1) {
    if (isOwn) return
    if (!isLoggedIn) {
      onRequireLogin()
      return
    }
    onVote(review.id, review.my_vote === value ? 0 : value)
  }

  return (
    <div className={styles.card} id={id}>
      <div className={styles.cardHead}>
        <span className={styles.cardAvatar}>{authorLetter}</span>
        <p className={styles.cardName}>{review.author_name || 'Покупатель'}</p>
        <span className={styles.cardDate}>{relativeDate(review.created_at)}</span>
      </div>

      <div className={styles.cardStars}>
        <StarRating value={review.rating} size={16} />
      </div>

      {review.text && (
        <>
          <p className={styles.cardCommentLabel}>Комментарий</p>
          <p className={expanded ? styles.cardText : `${styles.cardText} ${styles.cardTextClamped}`}>{review.text}</p>
          {review.text.length > 240 && (
            <button type="button" className={styles.cardMoreBtn} onClick={() => setExpanded((v) => !v)}>
              {expanded ? 'Свернуть' : 'Ещё'}
            </button>
          )}
        </>
      )}

      {review.tags.length > 0 && (
        <div className={styles.cardTags}>
          {review.tags.map((t) => (
            <span key={t.code} className={styles.cardTag}>
              {t.label}
            </span>
          ))}
        </div>
      )}

      {review.photos.length > 0 && (
        <div className={styles.cardPhotos}>
          {review.photos.slice(0, 5).map((url, i) => (
            <button
              key={`${url}-${i}`}
              type="button"
              className={styles.cardPhoto}
              onClick={() => onOpenPhoto(review.photos, i, review)}
              aria-label="Открыть фото"
            >
              <img src={url} alt="" />
            </button>
          ))}
        </div>
      )}

      <div className={styles.cardVotes}>
        <button
          type="button"
          className={review.my_vote === 1 ? `${styles.voteBtn} ${styles.voteBtnActive}` : styles.voteBtn}
          onClick={() => handleVote(1)}
          disabled={isOwn}
          aria-label="Полезно"
          aria-pressed={review.my_vote === 1}
        >
          <IconThumbUp size={16} stroke={1.8} /> {review.likes}
        </button>
        <button
          type="button"
          className={review.my_vote === -1 ? `${styles.voteBtn} ${styles.voteBtnActive}` : styles.voteBtn}
          onClick={() => handleVote(-1)}
          disabled={isOwn}
          aria-label="Не полезно"
          aria-pressed={review.my_vote === -1}
        >
          <IconThumbDown size={16} stroke={1.8} /> {review.dislikes}
        </button>
      </div>
    </div>
  )
}
