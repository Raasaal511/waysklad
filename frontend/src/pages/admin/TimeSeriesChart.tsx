import { useId, useMemo, useState } from 'react'
import styles from './TimeSeriesChart.module.css'

export interface ChartSeries {
  /** Столбики — основной ряд; линия — вторичный, со своей шкалой справа. */
  kind: 'bars' | 'line'
  label: string
  values: number[]
  /** CSS-цвет; по умолчанию --accent для столбиков и --board-new для линии. */
  color?: string
  /** Как показать значение в тултипе (например, деньги). */
  format?: (value: number) => string
}

interface TimeSeriesChartProps {
  /** ISO-даты, по одной на точку; длина задаёт ширину всех рядов. */
  dates: string[]
  series: ChartSeries[]
  height?: number
  /** Подпись под графиком, когда данных нет вовсе. */
  emptyLabel?: string
}

const PADDING = { top: 12, right: 44, bottom: 22, left: 44 }
const GRID_LINES = 4

function niceMax(value: number): number {
  if (value <= 0) return 1
  const magnitude = 10 ** Math.floor(Math.log10(value))
  const normalized = value / magnitude
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10
  return step * magnitude
}

/**
 * Делений столько, чтобы подписи не повторялись: при максимуме 2 шкала
 * «0 1 2», а не «0 1 1 2 2» — повторяющиеся числа выглядят как ошибка.
 */
function gridCount(max: number): number {
  return Math.max(1, Math.min(GRID_LINES, Math.round(max)))
}

function formatTick(iso: string): string {
  const date = new Date(iso)
  return `${date.getDate()}.${String(date.getMonth() + 1).padStart(2, '0')}`
}

/**
 * График по дням на инлайновом SVG: столбики и линия на общей оси X со
 * своими шкалами по Y. Без внешних библиотек — один компонент на обзор
 * платформы и карточку магазина.
 *
 * Ширина в пользовательских единицах фиксирована (viewBox), высота задаётся
 * пропом: так график ужимается под контейнер без горизонтального скролла на
 * телефоне, а подписи остаются читаемыми.
 */
export function TimeSeriesChart({
  dates,
  series,
  height = 220,
  emptyLabel = 'Нет данных за период',
}: TimeSeriesChartProps) {
  const [hover, setHover] = useState<number | null>(null)
  const clipId = useId()

  const width = 720
  const innerWidth = width - PADDING.left - PADDING.right
  const innerHeight = height - PADDING.top - PADDING.bottom

  const bars = series.find((s) => s.kind === 'bars')
  const line = series.find((s) => s.kind === 'line')

  const barsMax = useMemo(() => niceMax(Math.max(0, ...(bars?.values ?? [0]))), [bars])
  const lineMax = useMemo(() => niceMax(Math.max(0, ...(line?.values ?? [0]))), [line])

  const hasData = dates.length > 0 && series.some((s) => s.values.some((v) => v > 0))
  if (!hasData) {
    return <p className={styles.empty}>{emptyLabel}</p>
  }

  // одно число делений на обе шкалы: у каждой свой максимум, но линии сетки
  // общие, и разное число делений либо дублирует подписи, либо оставляет пустоты
  const grid = Math.min(gridCount(barsMax), line ? gridCount(lineMax) : GRID_LINES)
  const stepX = innerWidth / Math.max(dates.length, 1)
  const barWidth = Math.max(2, stepX * 0.6)

  const yBar = (value: number) => PADDING.top + innerHeight - (value / barsMax) * innerHeight
  const yLine = (value: number) => PADDING.top + innerHeight - (value / lineMax) * innerHeight
  const xCenter = (index: number) => PADDING.left + stepX * index + stepX / 2

  const linePath = line
    ? line.values
        .map((value, index) => `${index === 0 ? 'M' : 'L'} ${xCenter(index)} ${yLine(value)}`)
        .join(' ')
    : ''

  // подписи оси X: каждая пятая, чтобы 30 дат не слиплись
  const tickStep = Math.max(1, Math.round(dates.length / 6))

  return (
    <div className={styles.wrap}>
      {series.length > 1 && (
        <div className={styles.legend}>
          {series.map((s) => (
            <span key={s.label} className={styles.legendItem}>
              <span
                className={s.kind === 'bars' ? styles.legendBar : styles.legendLine}
                style={s.color ? { background: s.color } : undefined}
              />
              {s.label}
            </span>
          ))}
        </div>
      )}

      <svg
        className={styles.svg}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={series.map((s) => s.label).join(', ')}
        preserveAspectRatio="none"
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <clipPath id={clipId}>
            <rect x={PADDING.left} y={0} width={innerWidth} height={height} />
          </clipPath>
        </defs>

        {/* сетка и подписи левой шкалы (столбики) */}
        {Array.from({ length: grid + 1 }, (_, i) => {
          const value = (barsMax / grid) * i
          const y = yBar(value)
          return (
            <g key={i}>
              <line
                x1={PADDING.left}
                x2={width - PADDING.right}
                y1={y}
                y2={y}
                className={styles.grid}
              />
              <text x={PADDING.left - 8} y={y + 4} className={styles.axisLabel} textAnchor="end">
                {Math.round(value)}
              </text>
              {line && (
                <text
                  x={width - PADDING.right + 8}
                  y={y + 4}
                  className={styles.axisLabelSecondary}
                  textAnchor="start"
                >
                  {Math.round((lineMax / grid) * i)}
                </text>
              )}
            </g>
          )
        })}

        {bars && (
          <g clipPath={`url(#${clipId})`}>
            {bars.values.map((value, index) => (
              <rect
                key={index}
                x={xCenter(index) - barWidth / 2}
                y={yBar(value)}
                width={barWidth}
                height={Math.max(0, PADDING.top + innerHeight - yBar(value))}
                className={`${styles.bar} ${hover === index ? styles.barActive : ''}`}
                style={bars.color ? { fill: bars.color } : undefined}
              />
            ))}
          </g>
        )}

        {line && (
          <path
            d={linePath}
            className={styles.line}
            style={line.color ? { stroke: line.color } : undefined}
            clipPath={`url(#${clipId})`}
          />
        )}

        {/* подписи дат */}
        {dates.map((iso, index) =>
          index % tickStep === 0 ? (
            <text
              key={iso}
              x={xCenter(index)}
              y={height - 6}
              className={styles.axisLabel}
              textAnchor="middle"
            >
              {formatTick(iso)}
            </text>
          ) : null,
        )}

        {/* прозрачные полосы-ловушки: наведение по всей высоте, а не только по столбику */}
        {dates.map((iso, index) => (
          <rect
            key={`hit-${iso}`}
            x={PADDING.left + stepX * index}
            y={PADDING.top}
            width={stepX}
            height={innerHeight}
            fill="transparent"
            onMouseEnter={() => setHover(index)}
          />
        ))}

        {hover !== null && (
          <line
            x1={xCenter(hover)}
            x2={xCenter(hover)}
            y1={PADDING.top}
            y2={PADDING.top + innerHeight}
            className={styles.cursor}
          />
        )}
      </svg>

      {hover !== null && dates[hover] && (
        <div
          className={styles.tooltip}
          style={{ left: `${((xCenter(hover) - PADDING.left) / innerWidth) * 100}%` }}
        >
          <span className={styles.tooltipDate}>
            {new Date(dates[hover]).toLocaleDateString('ru-RU', {
              day: 'numeric',
              month: 'long',
            })}
          </span>
          {series.map((s) => (
            <span key={s.label} className={styles.tooltipRow}>
              {s.label}: <b>{s.format ? s.format(s.values[hover] ?? 0) : (s.values[hover] ?? 0)}</b>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
