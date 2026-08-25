import { IconPhoto } from '@tabler/icons-react'
import styles from './ProductPhoto.module.css'

export function ProductPhoto({ src, size = 40 }: { src: string; size?: number }) {
  if (!src) {
    return (
      <div className={`${styles['product-tile-photo']} ${styles['product-tile-photo-empty']}`}>
        <IconPhoto size={size} stroke={1.5} />
      </div>
    )
  }
  return <img src={src} alt="" className={styles['product-tile-photo']} loading="lazy" />
}
