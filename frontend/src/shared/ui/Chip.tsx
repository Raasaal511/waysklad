import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { IconX } from '@tabler/icons-react'
import styles from './Chip.module.css'

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean
  children: ReactNode
}

/** Общий чип-переключатель — фильтры (размер/цвет/рейтинг), категории. */
export function Chip({ active, children, className, ...rest }: ChipProps) {
  const classes = [styles.chip, active ? styles.active : '', className ?? ''].filter(Boolean).join(' ')
  return (
    <button type="button" className={classes} aria-pressed={active} {...rest}>
      {children}
    </button>
  )
}

interface RemovableChipProps {
  children: ReactNode
  onRemove: () => void
  removeLabel: string
}

/** Чип активного фильтра с крестиком — не переключатель, только «снять». Отдельная
 *  <button> для крестика (не вложенная в другую button — невалидный HTML/фокус). */
export function RemovableChip({ children, onRemove, removeLabel }: RemovableChipProps) {
  return (
    <span className={`${styles.chip} ${styles.removable}`}>
      {children}
      <button type="button" className={styles.remove} onClick={onRemove} aria-label={removeLabel}>
        <IconX size={12} stroke={2} />
      </button>
    </span>
  )
}
