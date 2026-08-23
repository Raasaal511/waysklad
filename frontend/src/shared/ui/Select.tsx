import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { IconChevronDown } from '@tabler/icons-react'
import layoutStyles from './Layout.module.css'

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

interface SelectProps {
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  className?: string
  disabled?: boolean
  required?: boolean
  id?: string
  'aria-label'?: string
}

export function Select({
  value,
  onChange,
  options,
  placeholder,
  className,
  disabled,
  required,
  id,
  'aria-label': ariaLabel,
}: SelectProps) {
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(0)
  const [menuStyle, setMenuStyle] = useState<{ top: number; left: number; width: number } | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLUListElement>(null)

  const selected = options.find((o) => o.value === value)

  useLayoutEffect(() => {
    if (!open) return
    function updatePosition() {
      const trigger = triggerRef.current
      if (!trigger) return
      const rect = trigger.getBoundingClientRect()
      setMenuStyle({
        top: rect.bottom + 4,
        left: rect.left,
        width: rect.width,
      })
    }
    updatePosition()
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [open])

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

  useEffect(() => {
    if (open) {
      const idx = options.findIndex((o) => o.value === value)
      setHighlighted(idx >= 0 ? idx : 0)
    }
  }, [open, options, value])

  function commit(option: SelectOption) {
    if (option.disabled) return
    onChange(option.value)
    setOpen(false)
    triggerRef.current?.focus()
  }

  function handleTriggerKeyDown(e: React.KeyboardEvent) {
    if (disabled) return
    if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault()
      setOpen(true)
      return
    }
    if (!open) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlighted((i) => Math.min(i + 1, options.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlighted((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      const option = options[highlighted]
      if (option) commit(option)
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
        onKeyDown={handleTriggerKeyDown}
      >
        <span className={selected ? layoutStyles.selectTriggerValue : layoutStyles.selectTriggerPlaceholder}>
          {selected ? selected.label : placeholder ?? ' '}
        </span>
        <IconChevronDown size={16} stroke={1.8} className={layoutStyles.selectTriggerIcon} />
      </button>

      {open &&
        menuStyle &&
        createPortal(
          <ul
            ref={menuRef}
            role="listbox"
            className={layoutStyles.selectMenu}
            style={{ top: menuStyle.top, left: menuStyle.left, minWidth: menuStyle.width }}
          >
            {options.map((option, i) => (
              <li
                key={option.value}
                role="option"
                aria-selected={option.value === value}
                className={[
                  layoutStyles.selectMenuItem,
                  i === highlighted ? layoutStyles.selectMenuItemHighlighted : '',
                  option.value === value ? layoutStyles.selectMenuItemSelected : '',
                  option.disabled ? layoutStyles.selectMenuItemDisabled : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                onMouseEnter={() => setHighlighted(i)}
                onClick={() => commit(option)}
              >
                {option.label}
              </li>
            ))}
          </ul>,
          document.body,
        )}
    </>
  )
}
