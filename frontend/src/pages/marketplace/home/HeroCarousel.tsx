import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react'
import type { Banner } from '../../../entities/marketplace/api'
import { Button } from '../../../shared/ui/Button'
import styles from './HeroCarousel.module.css'

interface Slide {
  key: string
  title: string
  subtitle: string
  buttonText: string
  link: string
  image: string
  imageMobile: string
  theme: 'light' | 'accent' | 'dark'
}

/** [Слово] в заголовке баннера → отдельным фрагментом с плашкой (см. M-F2 п.2). Без HTML — только текст. */
function renderTitle(title: string) {
  const parts = title.split(/(\[[^\]]+\])/g).filter(Boolean)
  return parts.map((part, i) => {
    const match = /^\[([^\]]+)\]$/.exec(part)
    if (!match) return <span key={i}>{part}</span>
    return (
      <span key={i} className={styles.highlight}>
        {match[1]}
      </span>
    )
  })
}

function isExternalLink(link: string) {
  return /^https?:\/\//.test(link)
}

const AUTOPLAY_MS = 6000

export function HeroCarousel({ banners }: { banners: Banner[] }) {
  const slides: Slide[] =
    banners.length > 0
      ? banners.map((b) => ({
          key: String(b.id),
          title: b.title,
          subtitle: b.subtitle,
          buttonText: b.button_text || 'Подробнее',
          link: b.link || '/marketplace',
          image: b.image,
          imageMobile: b.image_mobile || b.image,
          theme: b.theme,
        }))
      : [
          {
            key: 'default',
            title: 'Магазины [рядом] в одном месте',
            subtitle: 'Заказывайте онлайн — забирайте в магазине',
            buttonText: 'Смотреть магазины',
            link: '/marketplace/shops',
            // Временное решение до выполнения I1 (docs/ILLUSTRATIONS_PROMPTS.md):
            // /illustrations/hero-market.webp ещё не подготовлен (обрезка фона +
            // конвертация в WebP) — используем сырой исходник как есть.
            image: '/hero-banner.png',
            imageMobile: '/hero-banner.png',
            theme: 'light' as const,
          },
        ]

  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  const trackRef = useRef<HTMLDivElement>(null)
  const touchStartX = useRef<number | null>(null)
  const reducedMotion =
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

  useEffect(() => {
    setIndex((i) => Math.min(i, slides.length - 1))
  }, [slides.length])

  useEffect(() => {
    if (slides.length <= 1 || paused || reducedMotion) return
    function onVisibility() {
      setPaused(document.hidden)
    }
    document.addEventListener('visibilitychange', onVisibility)
    const t = setInterval(() => {
      if (!document.hidden) setIndex((i) => (i + 1) % slides.length)
    }, AUTOPLAY_MS)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [slides.length, paused, reducedMotion])

  function goTo(i: number) {
    setIndex((i + slides.length) % slides.length)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'ArrowLeft') {
      e.preventDefault()
      goTo(index - 1)
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      goTo(index + 1)
    }
  }

  function handleTouchStart(e: React.TouchEvent) {
    touchStartX.current = e.touches[0].clientX
  }
  function handleTouchEnd(e: React.TouchEvent) {
    if (touchStartX.current == null) return
    const dx = e.changedTouches[0].clientX - touchStartX.current
    touchStartX.current = null
    if (Math.abs(dx) < 40) return
    if (dx > 0) goTo(index - 1)
    else goTo(index + 1)
  }

  const single = slides.length === 1

  return (
    <div
      className={styles.wrap}
      role="region"
      aria-roledescription="carousel"
      aria-label="Баннеры маркетплейса"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      onKeyDown={handleKeyDown}
    >
      <div
        className={styles.viewport}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        <div
          ref={trackRef}
          className={styles.track}
          style={{ transform: `translateX(-${index * 100}%)` }}
          aria-live="off"
        >
          {slides.map((slide, i) => (
            <div
              key={slide.key}
              className={styles.slide}
              data-theme={slide.theme}
              aria-hidden={i !== index}
              aria-label={`${i + 1} из ${slides.length}`}
            >
              <div className={styles.slideText}>
                <h2 className={styles.slideTitle}>{renderTitle(slide.title)}</h2>
                {slide.subtitle && <p className={styles.slideSubtitle}>{slide.subtitle}</p>}
                {isExternalLink(slide.link) ? (
                  <a href={slide.link} target="_blank" rel="noopener noreferrer" tabIndex={i === index ? 0 : -1}>
                    {/* aria-hidden="true" на скрытом слайде не убирает фокусируемость вложенной
                        <button> — Lighthouse aria-hidden-focus — поэтому tabIndex дублируется на неё */}
                    <Button className={styles.slideBtn} tabIndex={-1}>
                      {slide.buttonText}
                    </Button>
                  </a>
                ) : (
                  <Link to={slide.link} tabIndex={i === index ? 0 : -1}>
                    <Button className={styles.slideBtn} tabIndex={-1}>
                      {slide.buttonText}
                    </Button>
                  </Link>
                )}
              </div>
              {slide.image && (
                <picture className={styles.slideImageWrap}>
                  <source media="(max-width: 767px)" srcSet={slide.imageMobile} />
                  <img src={slide.image} alt="" className={styles.slideImage} loading={i === 0 ? 'eager' : 'lazy'} />
                </picture>
              )}
            </div>
          ))}
        </div>
      </div>

      {!single && (
        <>
          <button
            type="button"
            className={`${styles.arrow} ${styles.arrowPrev}`}
            onClick={() => goTo(index - 1)}
            aria-label="Предыдущий баннер"
          >
            <IconChevronLeft size={20} stroke={2} />
          </button>
          <button
            type="button"
            className={`${styles.arrow} ${styles.arrowNext}`}
            onClick={() => goTo(index + 1)}
            aria-label="Следующий баннер"
          >
            <IconChevronRight size={20} stroke={2} />
          </button>
          <div className={styles.dots}>
            {slides.map((slide, i) => (
              <button
                key={slide.key}
                type="button"
                className={styles.dot}
                onClick={() => goTo(i)}
                aria-label={`Слайд ${i + 1}`}
                aria-current={i === index}
              >
                {/* масштабируется только визуальная точка внутри — hit-box кнопки
                    остаётся стабильным 24×24 и не наезжает на соседа (target-size) */}
                <span className={`${styles.dotMark} ${i === index ? styles.dotMarkActive : ''}`} />
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export function HeroCarouselSkeleton() {
  return <div className={styles.skeleton} aria-hidden="true" />
}
