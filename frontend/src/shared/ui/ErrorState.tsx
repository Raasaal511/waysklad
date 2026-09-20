import { Button } from './Button'
import styles from './EmptyState.module.css'

export type ErrorIllustrationName = 'error-404-not-found' | 'error-403-blocked'

interface ErrorStateProps {
  illustration: ErrorIllustrationName
  title: string
  description?: string
  actionLabel?: string
  onAction?: () => void
}

/** Общий экран ошибки: 404/403/сетевая — иллюстрация + текст + кнопка «Повторить»/«Все магазины». */
export function ErrorState({ illustration, title, description, actionLabel, onAction }: ErrorStateProps) {
  return (
    <div className={styles.wrap}>
      <img
        src={`/illustrations/${illustration}.png`}
        alt=""
        width={120}
        height={120}
        className={styles.illustration}
      />
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
