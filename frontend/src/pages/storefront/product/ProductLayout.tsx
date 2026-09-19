import type { ReactNode } from 'react'
import styles from './ProductPage.module.css'

interface ProductLayoutProps {
  gallery: ReactNode
  info: ReactNode
  aside: ReactNode
  below: ReactNode
}

/**
 * CSS grid карточки товара:
 * ≥1200px — три колонки (галерея / инфо+варианты / sticky-колонка).
 * 768–1199px — две колонки (галерея+инфо слева, sticky-колонка справа).
 * <768px — одна колонка, aside уходит вниз (после below).
 */
export function ProductLayout({ gallery, info, aside, below }: ProductLayoutProps) {
  return (
    <div className={styles.layout}>
      <div className={styles.areaGallery}>{gallery}</div>
      <div className={styles.areaInfo}>{info}</div>
      <div className={styles.areaAside}>{aside}</div>
      <div className={styles.areaBelow}>{below}</div>
    </div>
  )
}
