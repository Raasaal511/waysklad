import { IconCheck } from '@tabler/icons-react'
import { formatMoney } from '../../../shared/lib/format'
import pageStyles from './ProductPage.module.css'
import styles from './ProductAside.module.css'

interface MinOrderProgressProps {
  minOrderTotal: string
  currentTotal: number
}

/** Прогресс до минимальной суммы заказа магазина (вместо блока скидок wikkeo). */
export function MinOrderProgress({ minOrderTotal, currentTotal }: MinOrderProgressProps) {
  const min = Number(minOrderTotal)
  if (!Number.isFinite(min) || min <= 0) return null

  const remaining = Math.max(0, min - currentTotal)
  const done = remaining <= 0
  const percent = Math.min(100, (currentTotal / min) * 100)

  return (
    <div className={pageStyles.card}>
      {done ? (
        <p className={styles.progressDone}>
          <IconCheck size={16} stroke={2} /> Минимальная сумма набрана
        </p>
      ) : (
        <p className={styles.progressTitle}>До минимального заказа осталось {formatMoney(remaining.toFixed(2))} ₽</p>
      )}
      <div className={styles.progressBar}>
        <div className={styles.progressFill} style={{ width: `${percent}%` }} />
      </div>
      <div className={styles.progressLabels}>
        <span>0</span>
        <span>{formatMoney(minOrderTotal)} ₽</span>
      </div>
      <p className={styles.progressHint}>Минимальный заказ от {formatMoney(minOrderTotal)} ₽</p>
    </div>
  )
}
