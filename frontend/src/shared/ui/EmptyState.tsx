import { Button } from './Button'
import { Illustration, type IllustrationName } from './Illustration'
import styles from './EmptyState.module.css'

export type EmptyIllustrationName = IllustrationName

interface EmptyStateProps {
  /** Имя файла в public/illustrations (без картинки — просто текст: «ничего не найдено»). */
  illustration?: EmptyIllustrationName
  title: string
  description?: string
  actionLabel?: string
  onAction?: () => void
}

/** Общий пустой экран: иллюстрация (опционально) + заголовок + подзаголовок + кнопка действия. */
export function EmptyState({ illustration, title, description, actionLabel, onAction }: EmptyStateProps) {
  return (
    <div className={styles.wrap}>
      {illustration && <Illustration name={illustration} size={160} />}
      <h2 className={styles.title}>{title}</h2>
      {description && <p className={styles.description}>{description}</p>}
      {actionLabel && onAction && (
        <Button variant="secondary" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
