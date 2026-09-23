import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { IconChevronDown, IconPlus } from '@tabler/icons-react'
import layoutStyles from './Layout.module.css'
import type { SelectOption } from './Select'

interface CreatableSelectProps {
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  /** Создать значение из текста поиска. После успеха обычно обновляют options и вызывают onChange. */
  onCreate: (query: string) => void | Promise<void>
  /**
   * Пункт внизу списка при пустом поиске (например «+ Клиент»).
   * Без него создание видно только после ввода имени — на кассе это легко не заметить.
   */
  createActionLabel?: string
  /** Клик по createActionLabel — открыть форму с именем/телефоном и т.п. */
  onCreateAction?: () => void
  placeholder?: string
  searchPlaceholder?: string
  createLabel?: (query: string) => string
  className?: string
  disabled?: boolean
  required?: boolean
  id?: string
  'aria-label'?: string
}

export function CreatableSelect({
  value,
  onChange,
  options,
  onCreate,
  createActionLabel,
  onCreateAction,
  placeholder,
  searchPlaceholder = 'Поиск или новая…',
  createLabel = (query) => `Создать «${query}»`,
  className,
  disabled,
  required,
  id,
  'aria-label': ariaLabel,
}: CreatableSelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [highlighted, setHighlighted] = useState(0)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [menuStyle, setMenuStyle] = useState<{ top: number; left: number; width: number } | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const selected = options.find((o) => o.value === value)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return options
    return options.filter((o) => {
      const text = (o.searchText ?? o.label).trim().toLowerCase()
      return text.includes(q) || o.label.toLowerCase().includes(q)
    })
  }, [options, query])

  const trimmedQuery = query.trim()
  const exactMatch = options.some(
    (o) => (o.searchText ?? o.label).trim().toLowerCase() === trimmedQuery.toLowerCase(),
  )
  const canCreate = trimmedQuery.length > 0 && !exactMatch && !creating
  const showCreateAction =
    Boolean(createActionLabel && onCreateAction) && trimmedQuery.length === 0 && !creating

  type Row =
    | { kind: 'option'; option: SelectOption; index: number }
    | { kind: 'create'; query: string }
    | { kind: 'create-action' }

  const rows: Row[] = [
    ...filtered.map((option, index) => ({ kind: 'option' as const, option, index })),
    ...(canCreate ? [{ kind: 'create' as const, query: trimmedQuery }] : []),
    ...(showCreateAction ? [{ kind: 'create-action' as const }] : []),
  ]

  useLayoutEffect(() => {
    if (!open) return
    function updatePosition() {
      const trigger = triggerRef.current
      if (!trigger) return
      const rect = trigger.getBoundingClientRect()
      if (rect.bottom < 0 || rect.top > window.innerHeight) {
        setOpen(false)
        return
      }
      const margin = 8
      const dialog = trigger.closest('[role="dialog"]')
      const dialogRect = dialog?.getBoundingClientRect()
      const footer = dialog?.querySelector('[class*="modal-footer"]')
      const boundary = footer
        ? footer.getBoundingClientRect().top
        : dialogRect
          ? dialogRect.bottom
          : window.innerHeight
      const menuHeight = menuRef.current?.offsetHeight ?? 0
      const top = Math.max(margin, Math.min(rect.bottom + 4, boundary - menuHeight - margin))
      setMenuStyle({ top, left: rect.left, width: rect.width })
    }
    updatePosition()
    const raf = requestAnimationFrame(updatePosition)
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [open, filtered.length, canCreate, showCreateAction, createError])

  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node
      if (triggerRef.current?.contains(target) || menuRef.current?.contains(target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  useEffect(() => {
    if (open) {
      setQuery('')
      setCreateError(null)
      setHighlighted(0)
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  useEffect(() => {
    setHighlighted(0)
  }, [query])

  function close() {
    setOpen(false)
    triggerRef.current?.focus()
  }

  function commit(option: SelectOption) {
    if (option.disabled || creating) return
    onChange(option.value)
    close()
  }

  function runCreateAction() {
    close()
    onCreateAction?.()
  }

  async function createFromQuery(text: string) {
    if (creating || !text.trim()) return
    setCreating(true)
    setCreateError(null)
    try {
      await onCreate(text.trim())
      close()
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Не удалось создать')
    } finally {
      setCreating(false)
    }
  }

  function handleInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      close()
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlighted((i) => Math.min(i + 1, Math.max(rows.length - 1, 0)))
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlighted((i) => Math.max(i - 1, 0))
      return
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      e.stopPropagation()
      const row = rows[highlighted]
      if (!row) {
        if (canCreate) void createFromQuery(trimmedQuery)
        else if (showCreateAction) runCreateAction()
        return
      }
      if (row.kind === 'option') commit(row.option)
      else if (row.kind === 'create') void createFromQuery(row.query)
      else runCreateAction()
    }
  }

  const classes = [layoutStyles.selectTrigger]
  if (required && !value) classes.push('input-required')
  if (className) classes.push(className)

  return (
    <>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        className={classes.join(' ')}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        onClick={() => !disabled && setOpen((v) => !v)}
      >
        <span className={selected ? layoutStyles.selectTriggerValue : layoutStyles.selectTriggerPlaceholder}>
          {selected ? selected.label : placeholder ?? ' '}
        </span>
        <IconChevronDown size={16} stroke={1.8} className={layoutStyles.selectTriggerIcon} />
      </button>

      {open &&
        menuStyle &&
        createPortal(
          <div
            ref={menuRef}
            className={layoutStyles.selectMenu}
            style={{ top: menuStyle.top, left: menuStyle.left, minWidth: Math.max(menuStyle.width, 220) }}
          >
            <div className={layoutStyles.selectMenuSearch}>
              <input
                ref={inputRef}
                className={layoutStyles.selectMenuSearchInput}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleInputKeyDown}
                placeholder={searchPlaceholder}
                disabled={creating}
                aria-label={searchPlaceholder}
              />
            </div>
            <ul role="listbox" className={layoutStyles.selectMenuList}>
              {rows.length === 0 && (
                <li className={layoutStyles.selectMenuEmpty}>Ничего не найдено</li>
              )}
              {rows.map((row, i) => {
                if (row.kind === 'option') {
                  return (
                    <li
                      key={row.option.value || `opt-${row.index}`}
                      role="option"
                      aria-selected={row.option.value === value}
                      className={[
                        layoutStyles.selectMenuItem,
                        i === highlighted ? layoutStyles.selectMenuItemHighlighted : '',
                        row.option.value === value ? layoutStyles.selectMenuItemSelected : '',
                        row.option.disabled ? layoutStyles.selectMenuItemDisabled : '',
                      ]
                        .filter(Boolean)
                        .join(' ')}
                      onMouseEnter={() => setHighlighted(i)}
                      onClick={() => commit(row.option)}
                    >
                      {row.option.label}
                    </li>
                  )
                }
                if (row.kind === 'create-action') {
                  return (
                    <li
                      key="__create-action__"
                      role="option"
                      aria-selected={false}
                      className={[
                        layoutStyles.selectMenuItem,
                        layoutStyles.selectMenuCreate,
                        i === highlighted ? layoutStyles.selectMenuItemHighlighted : '',
                      ]
                        .filter(Boolean)
                        .join(' ')}
                      onMouseEnter={() => setHighlighted(i)}
                      onClick={runCreateAction}
                    >
                      <IconPlus size={14} stroke={1.8} />
                      {createActionLabel}
                    </li>
                  )
                }
                return (
                  <li
                    key="__create__"
                    role="option"
                    aria-selected={false}
                    className={[
                      layoutStyles.selectMenuItem,
                      layoutStyles.selectMenuCreate,
                      i === highlighted ? layoutStyles.selectMenuItemHighlighted : '',
                    ]
                      .filter(Boolean)
                      .join(' ')}
                    onMouseEnter={() => setHighlighted(i)}
                    onClick={() => void createFromQuery(row.query)}
                  >
                    <IconPlus size={14} stroke={1.8} />
                    {creating ? 'Создание…' : createLabel(row.query)}
                  </li>
                )
              })}
            </ul>
            {createError && <p className={layoutStyles.selectMenuError}>{createError}</p>}
          </div>,
          document.body,
        )}
    </>
  )
}
