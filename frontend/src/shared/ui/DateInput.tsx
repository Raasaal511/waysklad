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

export function DateInput({ value, onChange, min, max, className, disabled, required, id }: DateInputProps) {
  const [open, setOpen] = useState(false)
  const [menuStyle, setMenuStyle] = useState<{ top: number; left: number } | null>(null)
  const selected = parseISO(value)
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
      const menuWidth = 280 // совпадает с шириной .date-picker в DateInput.module.css
      const menuHeight = menuRef.current?.offsetHeight ?? 340
      const margin = 8
      const left = Math.min(
        Math.max(rect.left, margin),
        window.innerWidth - menuWidth - margin,
      )
      const fitsBelow = rect.bottom + 4 + menuHeight <= window.innerHeight - margin
      const top = fitsBelow
        ? rect.bottom + 4
        : Math.max(rect.top - 4 - menuHeight, margin)
      setMenuStyle({ top, left })
    }
    updatePosition()
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [open])

  // после первого рендера попапа известна его реальная высота — уточняем позицию
  useLayoutEffect(() => {
    if (!open || !menuStyle) return
    const trigger = triggerRef.current
    const menu = menuRef.current
    if (!trigger || !menu) return
    const rect = trigger.getBoundingClientRect()
    const menuHeight = menu.offsetHeight
    const margin = 8
    const fitsBelow = rect.bottom + 4 + menuHeight <= window.innerHeight - margin
    const top = fitsBelow ? rect.bottom + 4 : Math.max(rect.top - 4 - menuHeight, margin)
    if (top !== menuStyle.top) setMenuStyle((s) => (s ? { ...s, top } : s))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, menuStyle?.left])

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
    onChange(toISO(date))
    setOpen(false)
    triggerRef.current?.focus()
  }

  const classes = [layoutStyles.selectTrigger, styles['date-input-trigger']]
  if (required && !value) classes.push('input-required')
  if (className) classes.push(className)

  const cells = buildMonthGrid(viewYear, viewMonth)

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
          {value ? formatDisplay(value) : 'Выберите дату'}
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
              {cells.map((date, i) =>
                date ? (
                  <button
                    key={i}
                    type="button"
                    className={[
                      styles['date-picker-day'],
                      selected && isSameDay(date, selected) ? styles['date-picker-day-selected'] : '',
                      isSameDay(date, new Date()) ? styles['date-picker-day-today'] : '',
                    ]
                      .filter(Boolean)
                      .join(' ')}
                    disabled={isDisabled(date)}
                    onClick={() => commit(date)}
                  >
                    {date.getDate()}
                  </button>
                ) : (
                  <span key={i} />
                ),
              )}
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}
