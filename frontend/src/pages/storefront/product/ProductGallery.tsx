import { useEffect, useRef, useState } from 'react'
import {
  IconChevronLeft,
  IconChevronRight,
  IconChevronDown,
  IconChevronUp,
  IconShare,
  IconPhoto,
} from '@tabler/icons-react'
import { Lightbox } from '../../../shared/ui/Lightbox'
import styles from './ProductGallery.module.css'

const VISIBLE_THUMBS = 7

interface ProductGalleryProps {
  photos: string[]
  productName: string
  activeIndex: number
  onActiveIndexChange: (index: number) => void
  onShare?: () => void
}

/** Галерея карточки товара: лента миниатюр слева + большое фото (десктоп), свайп-лента (мобильный). */
export function ProductGallery({ photos, productName, activeIndex, onActiveIndexChange, onShare }: ProductGalleryProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false)
  const [thumbScroll, setThumbScroll] = useState(0)
  const mobileScrollerRef = useRef<HTMLDivElement>(null)

  const index = Math.min(activeIndex, Math.max(0, photos.length - 1))
  const hasMultiple = photos.length > 1

  useEffect(() => {
    // если индекс изменился извне (клик по варианту в F4) — прокручиваем мобильную ленту к нему
    const el = mobileScrollerRef.current
    if (!el) return
    const slide = el.children[index] as HTMLElement | undefined
    slide?.scrollIntoView({ behavior: 'auto', inline: 'start' })
  }, [index])

  function goPrev() {
    onActiveIndexChange((index - 1 + photos.length) % photos.length)
  }
  function goNext() {
    onActiveIndexChange((index + 1) % photos.length)
  }

  function handleMobileScroll() {
    const el = mobileScrollerRef.current
    if (!el) return
    const slideWidth = el.clientWidth || 1
    const i = Math.round(el.scrollLeft / slideWidth)
    if (i !== index && i >= 0 && i < photos.length) onActiveIndexChange(i)
  }

  const visibleThumbs = photos.slice(thumbScroll, thumbScroll + VISIBLE_THUMBS)
  const canScrollUp = thumbScroll > 0
  const canScrollDown = thumbScroll + VISIBLE_THUMBS < photos.length

  if (photos.length === 0) {
    return (
      <div className={styles.wrap}>
        <div className={styles.stage}>
          <div className={styles.stageEmpty}>
            <IconPhoto size={40} stroke={1.5} />
            <span>Нет фото</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className={styles.wrap}>
        {hasMultiple && (
          <div className={styles.thumbCol}>
            {canScrollUp && (
              <button
                type="button"
                className={styles.scrollBtn}
                onClick={() => setThumbScroll((s) => Math.max(0, s - 1))}
                aria-label="Прокрутить вверх"
              >
                <IconChevronUp size={16} stroke={1.8} />
              </button>
            )}
            <div className={styles.thumbList}>
              {visibleThumbs.map((url, i) => {
                const realIndex = thumbScroll + i
                return (
                  <button
                    key={`${url}-${realIndex}`}
                    type="button"
                    className={realIndex === index ? `${styles.thumbBtn} ${styles.thumbBtnActive}` : styles.thumbBtn}
                    onMouseEnter={() => onActiveIndexChange(realIndex)}
                    onClick={() => onActiveIndexChange(realIndex)}
                    aria-label={`Фото ${realIndex + 1}`}
                    aria-current={realIndex === index}
                  >
                    <img src={url} alt="" />
                  </button>
                )
              })}
            </div>
            {canScrollDown && (
              <button
                type="button"
                className={styles.scrollBtn}
                onClick={() => setThumbScroll((s) => Math.min(photos.length - VISIBLE_THUMBS, s + 1))}
                aria-label="Прокрутить вниз"
              >
                <IconChevronDown size={16} stroke={1.8} />
              </button>
            )}
          </div>
        )}

        {/* Десктоп: одно большое фото */}
        <div className={styles.stage}>
          <button
            type="button"
            className={styles.stageImgBtn}
            onClick={() => setLightboxOpen(true)}
            aria-label="Открыть фото на весь экран"
          >
            <img src={photos[index]} alt={productName} className={styles.stageImg} />
          </button>
          {hasMultiple && (
            <>
              <button type="button" className={`${styles.arrowBtn} ${styles.arrowPrev}`} onClick={goPrev} aria-label="Предыдущее фото">
                <IconChevronLeft size={20} stroke={1.8} />
              </button>
              <button type="button" className={`${styles.arrowBtn} ${styles.arrowNext}`} onClick={goNext} aria-label="Следующее фото">
                <IconChevronRight size={20} stroke={1.8} />
              </button>
              <span className={styles.counter}>
                {index + 1} / {photos.length}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Мобильный: свайп-лента, показывается через media query — десктопный wrap скрыт CSS */}
      <div className={styles.mobileWrap}>
        <div className={styles.mobileScroller} ref={mobileScrollerRef} onScroll={handleMobileScroll}>
          {photos.map((url, i) => (
            <div key={`${url}-${i}`} className={styles.mobileSlide} onClick={() => setLightboxOpen(true)}>
              <img src={url} alt={i === 0 ? productName : ''} />
            </div>
          ))}
        </div>
        {hasMultiple && (
          <div className={styles.dots}>
            {photos.map((_, i) => (
              <button
                key={i}
                type="button"
                className={i === index ? `${styles.dot} ${styles.dotActive}` : styles.dot}
                aria-label={`Фото ${i + 1}`}
                onClick={() => onActiveIndexChange(i)}
              />
            ))}
          </div>
        )}
        {onShare && (
          <button type="button" className={styles.shareOverlay} onClick={onShare} aria-label="Поделиться">
            <IconShare size={16} stroke={1.8} />
          </button>
        )}
      </div>

      {lightboxOpen && (
        <Lightbox photos={photos} index={index} onIndexChange={onActiveIndexChange} onClose={() => setLightboxOpen(false)} />
      )}
    </>
  )
}
