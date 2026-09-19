import { useState } from 'react'
import { Lightbox } from '../../../shared/ui/Lightbox'
import type { ReviewPhotoRef } from '../../../entities/review/api'
import pageStyles from './ProductPage.module.css'
import styles from './BuyerPhotos.module.css'

const MAX_TILES = 5

interface BuyerPhotosProps {
  photos: ReviewPhotoRef[]
}

/** «Фото покупателей» под галереей товара — квадраты из фото отзывов, последний с «+N». */
export function BuyerPhotos({ photos }: BuyerPhotosProps) {
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)

  if (photos.length === 0) return null

  const shown = photos.slice(0, MAX_TILES)
  const rest = photos.length - MAX_TILES

  return (
    <div className={pageStyles.card}>
      <h2 className={styles.title}>Фото покупателей</h2>
      <div className={styles.grid}>
        {shown.map((p, i) => {
          const isLastWithMore = i === MAX_TILES - 1 && rest > 0
          return (
            <button
              key={`${p.url}-${i}`}
              type="button"
              className={styles.tile}
              onClick={() => setLightboxIndex(i)}
              aria-label={isLastWithMore ? `Ещё ${rest} фото` : 'Открыть фото'}
            >
              <img src={p.url} alt="" />
              {isLastWithMore && <span className={styles.moreOverlay}>+{rest}</span>}
            </button>
          )
        })}
      </div>
      {lightboxIndex != null && (
        <Lightbox
          photos={photos.map((p) => p.url)}
          index={lightboxIndex}
          onIndexChange={setLightboxIndex}
          onClose={() => setLightboxIndex(null)}
        />
      )}
    </div>
  )
}
