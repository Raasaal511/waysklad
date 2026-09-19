import { useEffect, useRef, useState } from 'react'
import { IconX, IconPlus } from '@tabler/icons-react'
import { Modal } from '../../../shared/ui/Modal'
import { Button } from '../../../shared/ui/Button'
import { StarRating } from '../../../shared/ui/StarRating'
import { createReview, uploadReviewPhoto, getReviewTags, type ReviewTag } from '../../../entities/review/api'
import { ApiError } from '../../../shared/api/client'
import styles from './ReviewsSection.module.css'

const RATING_LABELS = ['Ужасно', 'Плохо', 'Нормально', 'Хорошо', 'Отлично']
const MAX_PHOTOS = 5
const MAX_TEXT = 2000

interface ReviewFormModalProps {
  requestId: number
  productId: number
  onClose: () => void
  onSuccess: () => void
}

export function ReviewFormModal({ requestId, productId, onClose, onSuccess }: ReviewFormModalProps) {
  const [rating, setRating] = useState(0)
  const [text, setText] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [allTags, setAllTags] = useState<ReviewTag[]>([])
  const [photos, setPhotos] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getReviewTags()
      .then(setAllTags)
      .catch(() => setAllTags([]))
  }, [])

  function toggleTag(code: string) {
    setTags((prev) => {
      if (prev.includes(code)) return prev.filter((c) => c !== code)
      if (prev.length >= 5) return prev
      return [...prev, code]
    })
  }

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || photos.length >= MAX_PHOTOS) return
    setUploading(true)
    setError(null)
    try {
      const { url } = await uploadReviewPhoto(file)
      setPhotos((prev) => [...prev, url])
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить фото')
    } finally {
      setUploading(false)
    }
  }

  function removePhoto(url: string) {
    setPhotos((prev) => prev.filter((p) => p !== url))
  }

  async function handleSubmit() {
    if (rating === 0) {
      setError('Поставьте оценку')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await createReview({
        storefront_request_id: requestId,
        product_id: productId,
        rating,
        text: text.trim(),
        photos,
        tags,
      })
      onSuccess()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось отправить отзыв')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal title="Написать отзыв" onClose={onClose}>
      <div className={styles.formField}>
        <span className={styles.formLabel}>Оценка</span>
        <StarRating value={rating} size={28} onChange={setRating} labels={RATING_LABELS} />
        {rating > 0 && <span className={styles.starLabel}>{RATING_LABELS[rating - 1]}</span>}
      </div>

      {allTags.length > 0 && (
        <div className={styles.formField}>
          <span className={styles.formLabel}>Что понравилось</span>
          <div className={styles.tagPickGrid}>
            {allTags.map((t) => {
              const active = tags.includes(t.code)
              return (
                <button
                  key={t.code}
                  type="button"
                  className={active ? `${styles.tagPick} ${styles.tagPickActive}` : styles.tagPick}
                  onClick={() => toggleTag(t.code)}
                  disabled={!active && tags.length >= 5}
                  aria-pressed={active}
                >
                  {t.label}
                </button>
              )
            })}
          </div>
        </div>
      )}

      <div className={styles.formField}>
        <span className={styles.formLabel}>Комментарий</span>
        <textarea
          className={styles.textarea}
          value={text}
          onChange={(e) => setText(e.target.value.slice(0, MAX_TEXT))}
          rows={4}
          placeholder="Расскажите о своих впечатлениях…"
        />
        <span className={styles.charCount}>
          {text.length} / {MAX_TEXT}
        </span>
      </div>

      <div className={styles.formField}>
        <span className={styles.formLabel}>Фото</span>
        <div className={styles.photoGrid}>
          {photos.map((url) => (
            <div key={url} className={styles.photoUploadTile}>
              <img src={url} alt="" />
              <button
                type="button"
                className={styles.photoRemoveBtn}
                onClick={() => removePhoto(url)}
                aria-label="Убрать фото"
              >
                <IconX size={12} stroke={2} />
              </button>
            </div>
          ))}
          {photos.length < MAX_PHOTOS && (
            <button
              type="button"
              className={styles.photoAddTile}
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              aria-label="Добавить фото"
            >
              <IconPlus size={20} stroke={1.8} />
            </button>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            style={{ display: 'none' }}
            onChange={handleFileSelect}
          />
        </div>
      </div>

      {error && <p className={styles.formError}>{error}</p>}

      <Button onClick={handleSubmit} disabled={submitting || uploading} style={{ width: '100%' }}>
        {submitting ? 'Отправка…' : 'Отправить отзыв'}
      </Button>
    </Modal>
  )
}
