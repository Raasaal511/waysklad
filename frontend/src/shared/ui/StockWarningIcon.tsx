import { IconAlertTriangle } from '@tabler/icons-react'
import styles from './StockWarningIcon.module.css'

/** Полупрозрачный жёлтый значок «остаток на исходе» с мгновенной CSS-подсказкой при наведении.
 * 'has-hint' — общий глобальный класс тултипа (см. index.css), используется
 * и IconButton, поэтому не переносится в CSS-модуль. */
export function StockWarningIcon({ label = 'Остаток на исходе — пора закупить' }: { label?: string }) {
  return (
    <span className={`${styles['stock-warning-icon']} has-hint`} data-hint={label}>
      <IconAlertTriangle size={14} stroke={2} aria-label={label} />
    </span>
  )
}
