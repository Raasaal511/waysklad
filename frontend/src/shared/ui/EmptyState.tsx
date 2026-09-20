import { Button } from './Button'
import styles from './EmptyState.module.css'

export type EmptyIllustrationName =
  | 'empty-archive'
  | 'empty-box'
  | 'empty-cart'
  | 'empty-shelf'
  | 'state-telegram-confirm'

interface EmptyStateProps {
  /** Имя файла в public/illustrations (без картинки — просто текст, см. п.4 блока «Д»: "ничего не найдено"). */
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
      {illustration && (
        <img
          src={`/illustrations/${illustration}.png`}
          alt=""
          width={120}
          height={120}
          className={styles.illustration}
        />
      )}
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
