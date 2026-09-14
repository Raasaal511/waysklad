import { IconPhoto } from '@tabler/icons-react'
import styles from './ProductPhoto.module.css'

export function ProductPhoto({ src, size = 84 }: { src: string; size?: number }) {
  const dims = { width: size, height: size } as const
  if (!src) {
    return (
      <div
        className={`${styles['product-tile-photo']} ${styles['product-tile-photo-empty']}`}
        style={dims}
      >
        <IconPhoto size={Math.max(18, Math.round(size * 0.42))} stroke={1.5} />
      </div>
    )
  }
  return <img src={src} alt="" className={styles['product-tile-photo']} style={dims} loading="lazy" />
}
