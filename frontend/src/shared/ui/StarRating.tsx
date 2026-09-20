import { useState } from 'react'
import { IconStar, IconStarFilled } from '@tabler/icons-react'
import styles from './StarRating.module.css'

interface StarRatingProps {
  value: number
  size?: number
  onChange?: (value: number) => void
  labels?: string[]
}

/**
 * Показ дробного рейтинга звёздами (var(--warning) / var(--border) для пустых).
 * С onChange становится выбором: role="radiogroup", управление стрелками, опциональные подписи.
 */
export function StarRating({ value, size = 16, onChange, labels }: StarRatingProps) {
  const [hovered, setHovered] = useState<number | null>(null)

  if (onChange) {
    const shown = hovered ?? value
    return (
      <div
        className={styles.row}
        role="radiogroup"
        aria-label="Оценка"
        onKeyDown={(e) => {
          if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
            e.preventDefault()
            onChange(Math.min(5, (value || 0) + 1))
          } else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
            e.preventDefault()
            onChange(Math.max(1, (value || 0) - 1))
          }
        }}
      >
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={value === n}
            aria-label={labels?.[n - 1] ?? `${n} из 5`}
            className={`${styles.interactive} ${n <= shown ? styles.interactiveFilled : ''}`}
            onMouseEnter={() => setHovered(n)}
            onMouseLeave={() => setHovered(null)}
            onClick={() => onChange(n)}
          >
            {n <= shown ? <IconStarFilled size={size} /> : <IconStar size={size} stroke={1.8} />}
          </button>
        ))}
      </div>
    )
  }

  const full = Math.floor(value)
  const hasHalf = value - full >= 0.25 && value - full < 0.75
  const roundedFull = value - full >= 0.75 ? full + 1 : full

  return (
    // role="img" — звёзды тут декоративны, aria-label целиком заменяет их одним
    // значением; без валидной role на <span> aria-label игнорируется (axe aria-prohibited-attr)
    <span className={styles.row} role="img" aria-label={`Рейтинг ${value.toFixed(1)} из 5`}>
      {[1, 2, 3, 4, 5].map((n) => {
        if (n <= roundedFull) {
          return <IconStarFilled key={n} size={size} className={styles.starFilled} />
        }
        if (hasHalf && n === roundedFull + 1) {
          return (
            <span key={n} className={styles.starHalfWrap}>
              <IconStar size={size} stroke={1.8} className={styles.star} />
              <span className={styles.starHalfFill}>
                <IconStarFilled size={size} />
              </span>
            </span>
          )
        }
        return <IconStar key={n} size={size} stroke={1.8} className={styles.star} />
      })}
    </span>
  )
}
