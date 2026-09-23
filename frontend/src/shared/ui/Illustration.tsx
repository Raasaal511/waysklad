import styles from './Illustration.module.css'

/**
 * Имена файлов в public/illustrations (без расширения).
 * Новые empty-* собираются в webp @1x/@2x; старые пока лежат PNG.
 */
export type IllustrationName =
  | 'empty-archive'
  | 'empty-box'
  | 'empty-cart'
  | 'empty-clients'
  | 'empty-reviews'
  | 'empty-sales'
  | 'empty-shelf'
  | 'empty-stock'
  | 'error-403-blocked'
  | 'error-404-not-found'
  | 'state-no-debts'
  | 'state-telegram-confirm'

/** Пиксельные размеры @1x (длинная сторона ≈ 200) — чтобы зарезервировать место
 * и не прыгала вёрстка до загрузки. Для PNG без webp — натуральные пропорции. */
export const ILLUSTRATION_SIZES: Record<IllustrationName, { w: number; h: number }> = {
  'empty-archive': { w: 200, h: 195 },
  'empty-box': { w: 200, h: 185 },
  'empty-cart': { w: 200, h: 160 },
  'empty-clients': { w: 200, h: 113 },
  'empty-reviews': { w: 200, h: 200 },
  'empty-sales': { w: 200, h: 144 },
  'empty-shelf': { w: 169, h: 200 },
  'empty-stock': { w: 200, h: 124 },
  'error-403-blocked': { w: 200, h: 187 },
  'error-404-not-found': { w: 200, h: 193 },
  'state-no-debts': { w: 200, h: 138 },
  'state-telegram-confirm': { w: 200, h: 172 },
}

/** Иллюстрации, для которых есть webp @1x + @2x в public/illustrations. */
const WEBP_NAMES = new Set<IllustrationName>([
  'empty-clients',
  'empty-sales',
  'empty-stock',
  'state-no-debts',
])

interface IllustrationProps {
  name: IllustrationName
  /** Длинная сторона в CSS-пикселях. По умолчанию 160 — как на empty-экранах. */
  size?: number
  className?: string
}

/** Иллюстрация empty/error: webp с retina-srcset где есть, иначе PNG;
 * в тёмной теме — светлая подложка, чтобы рисунок не тонул в фоне. */
export function Illustration({ name, size = 160, className }: IllustrationProps) {
  const { w, h } = ILLUSTRATION_SIZES[name]
  const scale = size / Math.max(w, h)
  const width = Math.max(1, Math.round(w * scale))
  const height = Math.max(1, Math.round(h * scale))
  const base = `/illustrations/${name}`
  const hasWebp = WEBP_NAMES.has(name)

  const img = (
    <img
      src={hasWebp ? `${base}.webp` : `${base}.png`}
      srcSet={hasWebp ? `${base}.webp 1x, ${base}@2x.webp 2x` : undefined}
      alt=""
      width={width}
      height={height}
      className={styles.img}
      decoding="async"
    />
  )

  return (
    <span
      className={[styles.wrap, className].filter(Boolean).join(' ')}
      style={{ width, height }}
    >
      {img}
    </span>
  )
}
