import { IconAlertTriangle } from '@tabler/icons-react'

/** Полупрозрачный жёлтый значок «остаток на исходе» с мгновенной CSS-подсказкой при наведении. */
export function StockWarningIcon({ label = 'Остаток на исходе — пора закупить' }: { label?: string }) {
  return (
    <span className="stock-warning-icon has-hint" data-hint={label}>
      <IconAlertTriangle size={14} stroke={2} aria-label={label} />
    </span>
  )
}
