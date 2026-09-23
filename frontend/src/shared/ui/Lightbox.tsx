import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { IconX, IconChevronLeft, IconChevronRight } from '@tabler/icons-react'
import styles from './Lightbox.module.css'

export interface LightboxCaption {
  authorName?: string
  rating?: number
  text?: string
  reviewAnchor?: string
}

interface LightboxProps {
  photos: string[]
  index: number
  onClose: () => void
  onIndexChange: (index: number) => void
  captions?: (LightboxCaption | undefined)[]
}

let lockCount = 0
function lockScroll() {
  if (lockCount === 0) document.body.style.overflow = 'hidden'
  lockCount++
}
function unlockScroll() {
  lockCount = Math.max(0, lockCount - 1)
  if (lockCount === 0) document.body.style.overflow = ''
}

/** Полноэкранный просмотр фото — общий для карточки товара и отзывов. Портал, фокус-ловушка, зум, свайп. */
export function Lightbox({ photos, index, onClose, onIndexChange, captions }: LightboxProps) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const closeBtnRef = useRef<HTMLButtonElement>(null)
  const previouslyFocused = useRef<HTMLElement | null>(null)
  const [zoomed, setZoomed] = useState(false)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const dragState = useRef<{ startX: number; startY: number; panX: number; panY: number } | null>(null)
  const touchState = useRef<{ startX: number; startY: number } | null>(null)

  const current = photos[index]
  const caption = captions?.[index]

  useEffect(() => {
    previouslyFocused.current = document.activeElement as HTMLElement
    lockScroll()
    closeBtnRef.current?.focus()
    return () => {
      unlockScroll()
      previouslyFocused.current?.focus?.()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    setZoomed(false)
    setPan({ x: 0, y: 0 })
  }, [index])

  function goPrev() {
    onIndexChange((index - 1 + photos.length) % photos.length)
  }
  function goNext() {
    onIndexChange((index + 1) % photos.length)
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowLeft') goPrev()
      else if (e.key === 'ArrowRight') goNext()
      else if (e.key === 'Tab') {
        const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
          'button, [href], input, [tabindex]:not([tabindex="-1"])',
        )
        if (!focusable || focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, photos.length])

  function handleDoubleClick() {
    setZoomed((z) => !z)
    setPan({ x: 0, y: 0 })
  }

  function handleMouseDown(e: React.MouseEvent) {
    if (!zoomed) return
    dragState.current = { startX: e.clientX, startY: e.clientY, panX: pan.x, panY: pan.y }
  }
  function handleMouseMove(e: React.MouseEvent) {
    if (!zoomed || !dragState.current) return
    const dx = e.clientX - dragState.current.startX
    const dy = e.clientY - dragState.current.startY
    setPan({ x: dragState.current.panX + dx, y: dragState.current.panY + dy })
  }
  function handleMouseUp() {
    dragState.current = null
  }

  function handleTouchStart(e: React.TouchEvent) {
    if (zoomed) return
    const t = e.touches[0]
    touchState.current = { startX: t.clientX, startY: t.clientY }
  }
  function handleTouchEnd(e: React.TouchEvent) {
    if (zoomed || !touchState.current) return
    const t = e.changedTouches[0]
    const dx = t.clientX - touchState.current.startX
    const dy = t.clientY - touchState.current.startY
    touchState.current = null
    if (Math.abs(dy) > 80 && Math.abs(dy) > Math.abs(dx)) {
      onClose()
      return
    }
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) {
      if (dx > 0) goPrev()
      else goNext()
    }
  }

  return createPortal(
    <div
      className={styles.overlay}
      role="dialog"
      aria-modal="true"
      aria-label="Просмотр фото"
      ref={dialogRef}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className={styles.topBar}>
        <span className={styles.counter}>
          {index + 1} / {photos.length}
        </span>
        <button type="button" ref={closeBtnRef} className={styles.closeBtn} onClick={onClose} aria-label="Закрыть">
          <IconX size={20} stroke={1.8} />
        </button>
      </div>

      <div
        className={styles.stage}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        {photos.length > 1 && (
          <button type="button" className={`${styles.navBtn} ${styles.navPrev}`} onClick={goPrev} aria-label="Предыдущее фото">
            <IconChevronLeft size={24} stroke={1.8} />
          </button>
        )}
        <div
          className={`${styles.stageImgWrap} ${zoomed ? styles.zoomed : ''}`}
          onDoubleClick={handleDoubleClick}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {current && (
            <img
              src={current}
              alt=""
              className={styles.stageImg}
              style={{
                transform: zoomed ? `scale(2) translate(${pan.x / 2}px, ${pan.y / 2}px)` : undefined,
              }}
              draggable={false}
            />
          )}
        </div>
        {photos.length > 1 && (
          <button type="button" className={`${styles.navBtn} ${styles.navNext}`} onClick={goNext} aria-label="Следующее фото">
            <IconChevronRight size={24} stroke={1.8} />
          </button>
        )}
      </div>

      {caption && (
        <div className={styles.caption}>
          {caption.authorName && (
            <p className={styles.captionAuthor}>
              {caption.authorName}
              {caption.rating != null && <span>· {'★'.repeat(Math.round(caption.rating))}</span>}
            </p>
          )}
          {caption.text && <p className={styles.captionText}>{caption.text}</p>}
          {caption.reviewAnchor && (
            <a
              className={styles.captionLink}
              href={caption.reviewAnchor}
              onClick={onClose}
            >
              К отзыву
            </a>
          )}
        </div>
      )}

      {photos.length > 1 && (
        <div className={styles.thumbStrip} role="tablist" aria-label="Все фото">
          {photos.map((url, i) => (
            <button
              key={`${url}-${i}`}
              type="button"
              role="tab"
              aria-selected={i === index}
              className={i === index ? `${styles.thumb} ${styles.thumbActive}` : styles.thumb}
              onClick={() => onIndexChange(i)}
            >
              <img src={url} alt="" />
            </button>
          ))}
        </div>
      )}
    </div>,
    document.body,
  )
}
