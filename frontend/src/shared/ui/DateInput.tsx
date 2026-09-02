import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { IconCalendar, IconChevronLeft, IconChevronRight } from '@tabler/icons-react'
import layoutStyles from './Layout.module.css'
import styles from './DateInput.module.css'

interface DateInputProps {
  value: string
  onChange: (value: string) => void
  min?: string
  max?: string
  className?: string
  disabled?: boolean
  required?: boolean
  id?: string
  /** Включает выбор промежутка вместо одной даты: value — начало, rangeEnd — конец.
   * Первый клик в календаре задаёт начало и сбрасывает конец, второй — завершает
   * диапазон (комитится через onRangeChange) и закрывает попап. */
  rangeEnd?: string
  onRangeChange?: (start: string, end: string) => void
}

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const MONTHS = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]

function parseISO(value: string): Date | null {
  if (!value) return null
  const [y, m, d] = value.split('-').map(Number)
  if (!y || !m || !d) return null
  return new Date(y, m - 1, d)
}

function toISO(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function formatDisplay(value: string): string {
  const date = parseISO(value)
  if (!date) return ''
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function buildMonthGrid(year: number, month: number): (Date | null)[] {
  const first = new Date(year, month, 1)
  const startOffset = (first.getDay() + 6) % 7 // понедельник = 0
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells: (Date | null)[] = []
  for (let i = 0; i < startOffset; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d))
  return cells
}

export function DateInput({
  value, onChange, min, max, className, disabled, required, id, rangeEnd, onRangeChange,
}: DateInputProps) {
  const isRange = onRangeChange != null
  const [open, setOpen] = useState(false)
  const [menuStyle, setMenuStyle] = useState<{ top: number; left: number } | null>(null)
  const selected = parseISO(value)
  const selectedEnd = parseISO(rangeEnd ?? '')
  // В процессе выбора диапазона (первый клик уже сделан, второй ещё нет) —
  // локальный "черновик" начала, который ещё не закоммичен через onRangeChange.
  const [rangeAnchor, setRangeAnchor] = useState<Date | null>(null)
  // Дата под курсором после выбора начала — превью диапазона до второго клика.
  const [hoverDate, setHoverDate] = useState<Date | null>(null)
  const [viewYear, setViewYear] = useState(() => (selected ?? new Date()).getFullYear())
  const [viewMonth, setViewMonth] = useState(() => (selected ?? new Date()).getMonth())
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const minDate = parseISO(min ?? '')
  const maxDate = parseISO(max ?? '')

  useLayoutEffect(() => {
    if (!open) return
    function updatePosition() {
      const trigger = triggerRef.current
      if (!trigger) return
      const rect = trigger.getBoundingClientRect()
      // кнопка полностью ушла за пределы окна (проскроллили мимо) — закрываем попап,
      // а не тащим его вникуда за кнопкой
      if (rect.bottom < 0 || rect.top > window.innerHeight) {
        setOpen(false)
        return
      }
      const menuWidth = 280 // совпадает с шириной .date-picker в DateInput.module.css
      const margin = 8
      const left = Math.min(
        Math.max(rect.left, margin),
        window.innerWidth - menuWidth - margin,
      )
      // если снизу не хватает места в границах модалки/окна, поднимаем попап
      // выше, чтобы он целиком поместился, а не обрезался нижним краем экрана
      const dialog = trigger.closest('[role="dialog"]')
      const dialogRect = dialog?.getBoundingClientRect()
      const footer = dialog?.querySelector('[class*="modal-footer"]')
      const boundary = footer
        ? footer.getBoundingClientRect().top
        : (dialogRect ? dialogRect.bottom : window.innerHeight)
      const menuHeight = menuRef.current?.offsetHeight ?? 0
      const top = Math.max(margin, Math.min(rect.bottom + 4, boundary - menuHeight - margin))
      setMenuStyle({ top, left })
    }
    updatePosition()
    // после первого прохода попап ещё не был в DOM, и его реальная высота не
    // учтена (menuHeight=0) — пересчитываем на следующем кадре, когда он уже отрендерен
    const raf = requestAnimationFrame(updatePosition)
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [open])

  useEffect(() => {
    if (!open) {
      setRangeAnchor(null)
      setHoverDate(null)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const base = selected ?? new Date()
    setViewYear(base.getFullYear())
    setViewMonth(base.getMonth())
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node
      if (triggerRef.current?.contains(target) || menuRef.current?.contains(target)) return
      setOpen(false)
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open])

  function isDisabled(date: Date): boolean {
    if (minDate && date < minDate) return true
    if (maxDate && date > maxDate) return true
    return false
  }

  function isSameDay(a: Date, b: Date): boolean {
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
  }

  function goToPrevMonth() {
    if (viewMonth === 0) {
      setViewMonth(11)
      setViewYear((y) => y - 1)
    } else {
      setViewMonth((m) => m - 1)
    }
  }

  function goToNextMonth() {
    if (viewMonth === 11) {
      setViewMonth(0)
      setViewYear((y) => y + 1)
    } else {
      setViewMonth((m) => m + 1)
    }
  }

  function commit(date: Date) {
    if (isDisabled(date)) return
    if (!isRange) {
      onChange(toISO(date))
      setOpen(false)
      triggerRef.current?.focus()
      return
    }
    if (!rangeAnchor) {
      // первый клик — задаём начало, пока не коммитим наружу (диапазон из
      // одной точки не имеет смысла для потребителя, ждём вторую дату)
      setRangeAnchor(date)
      return
    }
    const [start, end] = date < rangeAnchor ? [date, rangeAnchor] : [rangeAnchor, date]
    onRangeChange!(toISO(start), toISO(end))
    setRangeAnchor(null)
    setOpen(false)
    triggerRef.current?.focus()
  }

  const classes = [layoutStyles.selectTrigger, styles['date-input-trigger']]
  if (required && !value) classes.push('input-required')
  if (className) classes.push(className)

  const cells = buildMonthGrid(viewYear, viewMonth)

  // Диапазон для подсветки в гриде: во время выбора второй даты (rangeAnchor
  // задан) — превью от начала до даты под курсором, до второго клика; иначе —
  // уже закоммиченный диапазон value..rangeEnd.
  const previewEnd = rangeAnchor && hoverDate ? hoverDate : null
  const rangeStart = isRange ? (rangeAnchor ?? selected) : null
  const rangeFinish = isRange ? (rangeAnchor ? previewEnd : selectedEnd) : null

  return (
    <>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        className={classes.join(' ')}
        disabled={disabled}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => !disabled && setOpen((v) => !v)}
      >
        <IconCalendar size={16} stroke={1.8} className={styles['date-input-icon']} />
        <span className={value ? layoutStyles.selectTriggerValue : layoutStyles.selectTriggerPlaceholder}>
          {isRange
            ? value && rangeEnd
              ? value === rangeEnd
                ? formatDisplay(value)
                : `${formatDisplay(value)} — ${formatDisplay(rangeEnd)}`
              : 'Выберите дату'
            : value
              ? formatDisplay(value)
              : 'Выберите дату'}
        </span>
      </button>

      {open &&
        menuStyle &&
        createPortal(
          <div
            ref={menuRef}
            role="dialog"
            className={styles['date-picker']}
            style={{ top: menuStyle.top, left: menuStyle.left }}
          >
            <div className={styles['date-picker-header']}>
              <button
                type="button"
                className={styles['date-picker-nav']}
                onClick={goToPrevMonth}
                aria-label="Предыдущий месяц"
              >
                <IconChevronLeft size={16} stroke={1.8} />
              </button>
              <span className={styles['date-picker-title']}>
                {MONTHS[viewMonth]} {viewYear}
              </span>
              <button
                type="button"
                className={styles['date-picker-nav']}
                onClick={goToNextMonth}
                aria-label="Следующий месяц"
              >
                <IconChevronRight size={16} stroke={1.8} />
              </button>
            </div>
            <div className={styles['date-picker-weekdays']}>
              {WEEKDAYS.map((w) => (
                <span key={w}>{w}</span>
              ))}
            </div>
            <div className={styles['date-picker-grid']}>
              {cells.map((date, i) => {
                if (!date) return <span key={i} />
                // rangeFinish (hover-превью) может оказаться раньше rangeStart,
                // если навели на дату до уже выбранного начала — нормализуем
                // порядок, иначе диапазон "наоборот" просто не подсветится.
                const [rangeLo, rangeHi] =
                  rangeStart && rangeFinish
                    ? rangeStart <= rangeFinish
                      ? [rangeStart, rangeFinish]
                      : [rangeFinish, rangeStart]
                    : [null, null]
                const isEndpoint =
                  (rangeStart && isSameDay(date, rangeStart)) || (rangeFinish && isSameDay(date, rangeFinish))
                const isInRange = isRange && rangeLo && rangeHi && date > rangeLo && date < rangeHi
                return (
                  <button
                    key={i}
                    type="button"
                    className={[
                      styles['date-picker-day'],
                      !isRange && selected && isSameDay(date, selected) ? styles['date-picker-day-selected'] : '',
                      isRange && isEndpoint ? styles['date-picker-day-selected'] : '',
                      isRange && isInRange ? styles['date-picker-day-in-range'] : '',
                      isSameDay(date, new Date()) ? styles['date-picker-day-today'] : '',
                    ]
                      .filter(Boolean)
                      .join(' ')}
                    disabled={isDisabled(date)}
                    onClick={() => commit(date)}
                    onMouseEnter={() => rangeAnchor && setHoverDate(date)}
                  >
                    {date.getDate()}
                  </button>
                )
              })}
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}
