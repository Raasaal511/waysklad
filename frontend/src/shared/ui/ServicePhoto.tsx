import type { CSSProperties } from 'react'
import styles from './ServicePhoto.module.css'

// мягкие оттенки для буквы-заглушки; выбор по названию — у одной услуги
// цвет всегда один и тот же, а соседние карточки не сливаются в одно пятно
const TINTS = ['#1f8a5b', '#2f6fde', '#d0811a', '#7b4fd6', '#d2457e', '#16958a']

function tintFor(name: string) {
  let hash = 0
  for (const ch of name.trim().toLowerCase()) hash = (hash * 31 + ch.charCodeAt(0)) | 0
  return TINTS[Math.abs(hash) % TINTS.length]
}

/**
 * Фото услуги или, если его нет, крупная первая буква названия.
 * Услугу часто нечем снять («консультация», «замер»), а серая иконка
 * «нет фото» в каждой карточке выглядит как недоделка — буква на мягком
 * цветном фоне читается как задуманный знак. Одна и та же заглушка
 * в кабинете и на витрине, чтобы владелец видел то же, что покупатель.
 */
export function ServicePhoto({
  src,
  name,
  size,
  className,
}: {
  src: string
  name: string
  /** Сторона квадрата в px; без неё растягивается по контейнеру. */
  size?: number
  className?: string
}) {
  const dims = size ? { width: size, height: size } : undefined
  const classes = [styles.photo, className].filter(Boolean).join(' ')
  if (src) {
    return <img src={src} alt="" className={classes} style={dims} loading="lazy" />
  }
  const letter = name.trim().charAt(0).toUpperCase() || '·'
  const style = {
    ...dims,
    fontSize: size ? Math.round(size * 0.44) : undefined,
    '--tint': tintFor(name),
  } as CSSProperties
  return (
    <div className={`${classes} ${styles.letter}`} style={style} aria-hidden="true">
      <span key={letter} className={styles.glyph}>
        {letter}
      </span>
    </div>
  )
}
