import { IconMinus, IconPlus } from '@tabler/icons-react'
import styles from './QtyStepper.module.css'

interface QtyStepperProps {
  value: number | string
  onStep: (delta: 1 | -1) => void
  onDirectInput: (raw: string) => void
  inputAriaLabel: string
  decreaseAriaLabel?: string
  increaseAriaLabel?: string
  disableDecrease?: boolean
  /** decimal — для весовых товаров в корзине (0,5 кг) */
  inputMode?: 'numeric' | 'decimal'
}

/** Степпер количества витрины: товар без вариантов, строка варианта и корзина —
 *  один компонент (раньше корзина обходилась голым текстовым полем). */
export function QtyStepper({
  value,
  onStep,
  onDirectInput,
  inputAriaLabel,
  decreaseAriaLabel = 'Уменьшить количество',
  increaseAriaLabel = 'Увеличить количество',
  disableDecrease,
  inputMode = 'numeric',
}: QtyStepperProps) {
  return (
    <div className={styles.stepper}>
      <button
        type="button"
        className={`${styles.stepBtn} ${styles.stepMinus}`}
        onClick={() => onStep(-1)}
        aria-label={decreaseAriaLabel}
        disabled={disableDecrease}
      >
        <IconMinus size={18} stroke={2} />
      </button>
      <input
        className={styles.stepValue}
        type="text"
        inputMode={inputMode}
        value={String(value)}
        onChange={(e) => onDirectInput(e.target.value)}
        aria-label={inputAriaLabel}
      />
      <button type="button" className={`${styles.stepBtn} ${styles.stepPlus}`} onClick={() => onStep(1)} aria-label={increaseAriaLabel}>
        <IconPlus size={18} stroke={2} />
      </button>
    </div>
  )
}
