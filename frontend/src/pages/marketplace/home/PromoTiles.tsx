import { Link } from 'react-router-dom'
import { IconArrowRight, IconStarFilled } from '@tabler/icons-react'
import type { Banner } from '../../../entities/marketplace/api'
import styles from './PromoTiles.module.css'

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

function BannerTile({ banner }: { banner: Banner }) {
  const content = (
    <>
      <div className={styles.tileText}>
        <h3 className={styles.tileTitle}>{renderTitle(banner.title)}</h3>
        {banner.subtitle && <p className={styles.tileSubtitle}>{banner.subtitle}</p>}
        <span className={styles.tileBtn}>
          {banner.button_text || 'Перейти'} <IconArrowRight size={16} stroke={2} className={styles.tileBtnArrow} />
        </span>
      </div>
      {banner.image && <img src={banner.image} alt="" className={styles.tileImage} loading="lazy" />}
    </>
  )
  const className = `${styles.tile} ${styles.tileBanner}`
  return isExternalLink(banner.link) ? (
    <a href={banner.link} target="_blank" rel="noopener noreferrer" className={className} data-theme={banner.theme}>
      {content}
    </a>
  ) : (
    <Link to={banner.link || '/marketplace'} className={className} data-theme={banner.theme}>
      {content}
    </Link>
  )
}

/** Композиция из звёзд и карточки-отзыва на CSS вместо иллюстрации — M-F2 п.4б. */
function ReviewsIllustration() {
  return (
    <div className={styles.reviewsArt} aria-hidden="true">
      <div className={styles.reviewsStars}>
        <IconStarFilled size={22} />
        <IconStarFilled size={28} />
        <IconStarFilled size={22} />
      </div>
      <div className={styles.reviewsCard}>
        <div className={styles.reviewsCardLine} style={{ width: '70%' }} />
        <div className={styles.reviewsCardLine} style={{ width: '90%' }} />
        <div className={styles.reviewsCardLine} style={{ width: '50%' }} />
      </div>
    </div>
  )
}

/** Две промо-плитки — из banners.promo или встроенные по умолчанию. M-F2 п.4. */
export function PromoTiles({ promo }: { promo: Banner[] }) {
  if (promo.length >= 2) {
    return (
      <div className={styles.grid}>
        <BannerTile banner={promo[0]} />
        <BannerTile banner={promo[1]} />
      </div>
    )
  }

  return (
    <div className={styles.grid}>
      <Link to="/login?mode=register" className={`${styles.tile} ${styles.tileOnboarding}`}>
        <div className={styles.tileText}>
          <h3 className={styles.tileTitle}>Откройте магазин бесплатно</h3>
          <p className={styles.tileSubtitle}>Учёт, продажи и своя витрина. 0 ₽ навсегда</p>
          <span className={styles.tileBtnLight}>
            Начать <IconArrowRight size={16} stroke={2} className={styles.tileBtnArrow} />
          </span>
        </div>
        {/* Временное решение до I1: онбординг-иллюстрация ещё не обрезана и не в WebP,
            используем сырой public/onbarding.png как есть (см. отчёт P5). */}
        <img src="/onbarding.png" alt="" className={styles.tileImage} loading="lazy" />
      </Link>
      <Link to="/marketplace?section=top_rated" className={`${styles.tile} ${styles.tileReviews}`}>
        <div className={styles.tileText}>
          <h3 className={styles.tileTitle}>Отзывы реальных покупателей</h3>
          <p className={styles.tileSubtitle}>Оставить отзыв можно только после покупки</p>
          <span className={styles.tileBtn}>
            Смотреть <IconArrowRight size={16} stroke={2} className={styles.tileBtnArrow} />
          </span>
        </div>
        <ReviewsIllustration />
      </Link>
    </div>
  )
}

export function PromoTilesSkeleton() {
  return (
    <div className={styles.grid} aria-hidden="true">
      <div className={`${styles.tile} ${styles.skeletonTile}`} />
      <div className={`${styles.tile} ${styles.skeletonTile}`} />
    </div>
  )
}
