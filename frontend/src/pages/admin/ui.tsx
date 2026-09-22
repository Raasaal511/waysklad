import type { ReactNode } from 'react'
import { IconArrowDownRight, IconArrowUpRight } from '@tabler/icons-react'
import styles from './ui.module.css'

interface CardProps {
  title?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}

/** Базовая карточка раздела: фон --bg, radius 16, padding 20, рамка 1px. */
export function Card({ title, action, children, className }: CardProps) {
  return (
    <section className={`${styles.card} ${className ?? ''}`}>
      {(title || action) && (
        <header className={styles.cardHead}>
          {title && <h2 className={styles.cardTitle}>{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </section>
  )
}

interface MetricProps {
  label: string
  /** null/undefined → «нет данных», а не «0». */
  value: string | null | undefined
  /** Вторая строка под значением — сумма, доля, уточнение. */
  note?: string | null
  /** Изменение к прошлому периоду в процентах; null — сравнивать не с чем. */
  delta?: number | null
  /** Для метрик, где рост — это плохо (ошибки, заблокированные). */
  invertDelta?: boolean
}

/** Крупный показатель: значение 32/700, подпись 13/600, дельта к периоду. */
export function Metric({ label, value, note, delta, invertDelta }: MetricProps) {
  const good = delta == null ? null : invertDelta ? delta <= 0 : delta >= 0
  const display = value == null || value === '' ? 'нет данных' : value
  return (
    <div className={styles.metric}>
      <span className={styles.metricLabel}>{label}</span>
      <span className={styles.metricValue}>{display}</span>
      <div className={styles.metricFoot}>
        {note != null && note !== '' && <span className={styles.metricNote}>{note}</span>}
        {delta != null && Number.isFinite(delta) && (
          <span
            className={`${styles.delta} ${good ? styles.deltaUp : styles.deltaDown}`}
            title="Изменение к прошлому периоду"
          >
            {delta >= 0 ? (
              <IconArrowUpRight size={14} stroke={2} />
            ) : (
              <IconArrowDownRight size={14} stroke={2} />
            )}
            {Math.abs(Math.round(delta))}%
          </span>
        )}
      </div>
    </div>
  )
}

/** Ряд показателей: сетка подстраивается под число карточек, не растягивается. */
export function MetricRow({ children }: { children: ReactNode }) {
  return <div className={styles.metricRow}>{children}</div>
}

/** Скелетон блока на время загрузки. */
export function Skeleton({ height = 120 }: { height?: number }) {
  return <div className={styles.skeleton} style={{ height }} aria-hidden="true" />
}

/**
 * Ошибка загрузки внутри блока, а не на всю страницу: остальные разделы
 * данные уже показали, и терять их из-за одного упавшего запроса незачем.
 */
export function BlockError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className={styles.blockError}>
      <p className={styles.blockErrorText}>{message}</p>
      {onRetry && (
        <button type="button" className={styles.retryBtn} onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  )
}

/** Пустое состояние блока — просто текст, без иллюстраций (B4). */
export function EmptyBlock({ text }: { text: string }) {
  return <p className={styles.emptyBlock}>{text}</p>
}

export type StatusTone = 'ok' | 'warn' | 'danger' | 'muted'

/** Цветная точка с подписью: статус магазина, светофор сервиса. */
export function StatusDot({ tone, label }: { tone: StatusTone; label: string }) {
  return (
    <span className={styles.statusDot} data-tone={tone}>
      <span className={styles.dot} />
      {label}
    </span>
  )
}

/** «нет данных» вместо нуля там, где бэкенд честно вернул null. */
export function NoData() {
  return <span className={styles.noData}>нет данных</span>
}
