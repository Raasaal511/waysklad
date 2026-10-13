import styles from './ServicePhoto.module.css'

/**
 * Фото услуги или, если его нет, крупная первая буква названия.
 * Услугу часто нечем снять («консультация», «замер»), а серая иконка
 * «нет фото» в каждой карточке выглядит как недоделка — буква на мягком
 * акцентном фоне читается как задуманный знак. Одна и та же заглушка
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
  return (
    <div
      className={`${classes} ${styles.letter}`}
      style={{ ...dims, fontSize: size ? Math.round(size * 0.44) : undefined }}
      aria-hidden="true"
    >
      {letter}
    </div>
  )
}
