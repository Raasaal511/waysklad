import { IconPhoto } from '@tabler/icons-react'
import styles from './ProductPhoto.module.css'

// Глобальные имена рядом с модульными: страницы подгоняют фото под свою сетку
// через :global(.product-tile-photo) — у модульных классов в сборке другие имена,
// и без этого заглушка «нет фото» оставалась size×size посреди большой карточки.
const GLOBAL = 'product-tile-photo'
const GLOBAL_EMPTY = 'product-tile-photo-empty'

export function ProductPhoto({ src, size = 84 }: { src: string; size?: number }) {
  const dims = { width: size, height: size } as const
  if (!src) {
    return (
      <div
        className={`${GLOBAL} ${GLOBAL_EMPTY} ${styles['product-tile-photo']} ${styles['product-tile-photo-empty']}`}
        style={dims}
      >
        <IconPhoto size={Math.max(18, Math.round(size * 0.42))} stroke={1.5} />
      </div>
    )
  }
  return <img src={src} alt="" className={`${GLOBAL} ${styles['product-tile-photo']}`} style={dims} loading="lazy" />
}
