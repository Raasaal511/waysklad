import { useState, type ReactNode } from 'react'
import { IconChartBarOff } from '@tabler/icons-react'
import styles from './BarChart.module.css'

export interface BarChartPoint {
  label: string
  /** Короткая версия подписи для оси, если полная не помещается под баром
   * (тултип и детальная панель всегда используют полный `label`). */
  axisLabel?: string
  value: number
  tooltip?: ReactNode
  detail?: ReactNode
}

interface BarChartProps {
  points: BarChartPoint[]
  height?: number
  formatValue?: (value: number) => string
  emptyMessage?: string
}

const GRID_LINES = 4

/** Лёгкая столбчатая диаграмма без внешних зависимостей — с осью значений,
 * hover-тултипом (десктоп) и кликабельным выбором точки, который фиксирует
 * подробную панель под графиком (работает и тапом на мобильном). */
export function BarChart({ points, height = 200, formatValue, emptyMessage = 'Нет данных' }: BarChartProps) {
  const [hovered, setHovered] = useState<number | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const fmt = formatValue ?? ((v: number) => String(v))

  const hasData = points.length > 0 && points.some((p) => p.value > 0)
  if (!hasData) {
    return (
      <div className={styles.wrap}>
        <div className={styles.empty}>
          <span className={styles.emptyIcon} aria-hidden="true">
            <IconChartBarOff size={22} stroke={1.7} />
          </span>
          <p>{emptyMessage}</p>
        </div>
      </div>
    )
  }

  const max = Math.max(...points.map((p) => p.value), 0)
  const niceMax = max > 0 ? niceCeiling(max) : 1
  const sparse = points.length <= 4
  const lastNonEmptyIndex = (() => {
    for (let i = points.length - 1; i >= 0; i--) {
      if (points[i].value > 0) return i
    }
    return points.length - 1
  })()
  const activeIndex = selected ?? lastNonEmptyIndex
  const activePoint = activeIndex != null ? points[activeIndex] : null

  const gridValues = Array.from({ length: GRID_LINES + 1 }, (_, i) => (niceMax / GRID_LINES) * (GRID_LINES - i))
  // При большом числе точек подпись под каждым баром не помещается и режется
  // многоточием — показываем только каждую N-ю. Подпись живёт в той же
  // колонке, что и бар (не в отдельном ряду), поэтому её позиция всегда
  // совпадает со своим столбцом независимо от прореживания.
  const labelStep = points.length <= 8 ? 1 : Math.ceil(points.length / 8)

  return (
    <div className={styles.wrap}>
      <div className={styles.plotRow}>
        <div className={styles.yAxis} style={{ height }}>
          {gridValues.map((v, i) => (
            <span key={i} className={styles.yAxisLabel}>
              {fmt(v)}
            </span>
          ))}
        </div>
        <div className={styles.plotArea}>
          <div className={styles.gridLines} style={{ height }}>
            {gridValues.map((_, i) => (
              <div key={i} className={styles.gridLine} />
            ))}
          </div>
          <div className={`${styles.plot}${sparse ? ` ${styles.plotSparse}` : ''}`}>
            {points.map((p, i) => {
              const pct = niceMax > 0 ? (p.value / niceMax) * 100 : 0
              const isHovered = hovered === i
              const isActive = activeIndex === i
              return (
                <button
                  key={i}
                  type="button"
                  className={styles.barCol}
                  style={sparse ? undefined : { width: `${100 / points.length}%` }}
                  onMouseEnter={() => setHovered(i)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => setSelected(i)}
                >
                  {isHovered && (
                    <div className={styles.tooltip}>
                      {p.tooltip ?? (
                        <>
                          <strong>{fmt(p.value)}</strong>
                          <span>{p.label}</span>
                        </>
                      )}
                    </div>
                  )}
                  <div className={styles.barTrack} style={{ height }}>
                    <div
                      className={isHovered || isActive ? styles.barHovered : styles.bar}
                      style={{ height: `${Math.max(pct, p.value > 0 ? 1.5 : 0)}%` }}
                    />
                  </div>
                  <span className={isActive ? styles.axisLabelActive : styles.axisLabel}>
                    {isActive || i % labelStep === 0 ? (p.axisLabel ?? p.label) : ''}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      </div>
      {activePoint?.detail && (
        <div className={styles.detailPanel}>
          <div className={styles.detailPanelAccent} />
          {activePoint.detail}
        </div>
      )}
    </div>
  )
}

/** Округляет максимум графика вверх до «красивого» числа (1/2/5 × 10^n),
 * чтобы деления оси не выглядели случайными (напр. 6400 → 8000, не 6413). */
function niceCeiling(value: number): number {
  const exponent = Math.floor(Math.log10(value))
  const magnitude = Math.pow(10, exponent)
  const fraction = value / magnitude
  let niceFraction: number
  if (fraction <= 1) niceFraction = 1
  else if (fraction <= 2) niceFraction = 2
  else if (fraction <= 5) niceFraction = 5
  else niceFraction = 10
  return niceFraction * magnitude
}
