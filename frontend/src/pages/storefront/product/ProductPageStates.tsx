import { Link } from 'react-router-dom'
import { Button } from '../../../shared/ui/Button'
import styles from './ProductPageStates.module.css'

/** Skeleton всей карточки товара по сетке — показывается на время первой загрузки. */
export function ProductPageSkeleton() {
  return (
    <div className={styles.skeletonLayout}>
      <div className={`${styles.skeletonBlock} ${styles.skeletonGallery}`} />
      <div className={styles.skeletonInfo}>
        <div className={`${styles.skeletonBlock} ${styles.skeletonInfoBlock}`} />
        <div className={`${styles.skeletonBlock} ${styles.skeletonInfoBlock}`} />
      </div>
      <div className={styles.skeletonAside}>
        <div className={`${styles.skeletonBlock} ${styles.skeletonAsideBlock}`} />
        <div className={`${styles.skeletonBlock} ${styles.skeletonAsideBlock}`} />
      </div>
    </div>
  )
}

interface ProductPageErrorProps {
  status: number | null
  slug: string
}

/** 404 / 403 / сеть — разные иллюстрации и тексты по коду ошибки. */
export function ProductPageError({ status, slug }: ProductPageErrorProps) {
  if (status === 404) {
    return (
      <div className={styles.stateWrap}>
        <img src="/illustrations/error-404-not-found.png" alt="" />
        <p className={styles.stateTitle}>Товар не найден или скрыт</p>
        <Link to={`/store/${slug}`}>
          <Button>Вернуться в витрину</Button>
        </Link>
      </div>
    )
  }
  if (status === 403) {
    return (
      <div className={styles.stateWrap}>
        <img src="/illustrations/error-403-blocked.png" alt="" />
        <p className={styles.stateTitle}>Магазин временно недоступен</p>
      </div>
    )
  }
  return (
    <div className={styles.stateWrap}>
      <p className={styles.stateTitle}>Не удалось загрузить</p>
      <Button onClick={() => window.location.reload()}>Повторить</Button>
    </div>
  )
}
