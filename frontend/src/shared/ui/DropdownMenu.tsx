import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

export interface DropdownMenuItem {
  key: string
  label: ReactNode
  onSelect: () => void
  disabled?: boolean
}

interface DropdownMenuProps {
  trigger: ReactNode
  items: DropdownMenuItem[]
  align?: 'left' | 'right'
}

export function DropdownMenu({ trigger, items, align = 'left' }: DropdownMenuProps) {
  const [open, setOpen] = useState(false)
  const [menuStyle, setMenuStyle] = useState<{ top: number; left: number } | null>(null)
  const triggerRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLUListElement>(null)

  useLayoutEffect(() => {
    if (!open) return
    function updatePosition() {
      const trigger = triggerRef.current
      const menu = menuRef.current
      if (!trigger) return
      const rect = trigger.getBoundingClientRect()
      const menuWidth = menu?.offsetWidth ?? 0
      setMenuStyle({
        top: rect.bottom + 4,
        left: align === 'right' ? rect.right - menuWidth : rect.left,
      })
    }
    // При первом открытии портал с меню ещё не смонтирован в этом же эффекте
    // (menuRef.current === null), поэтому ширина неизвестна — пересчитываем
    // ещё раз сразу после монтирования, когда реальная ширина уже доступна.
    updatePosition()
    const raf = requestAnimationFrame(updatePosition)
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [open, align])

  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node
      if (triggerRef.current?.contains(target) || menuRef.current?.contains(target)) return
      setOpen(false)
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open])

  function commit(item: DropdownMenuItem) {
    if (item.disabled) return
    setOpen(false)
    item.onSelect()
  }

  return (
    <>
      <div ref={triggerRef} onClick={() => setOpen((v) => !v)}>
        {trigger}
      </div>

      {open &&
        menuStyle &&
        createPortal(
          <ul
            ref={menuRef}
            role="menu"
            className="select-menu"
            style={{ top: menuStyle.top, left: menuStyle.left }}
          >
            {items.map((item) => (
              <li
                key={item.key}
                role="menuitem"
                className={`select-menu-item${item.disabled ? ' select-menu-item-disabled' : ''}`}
                onClick={() => commit(item)}
              >
                {item.label}
              </li>
            ))}
          </ul>,
          document.body,
        )}
    </>
  )
}
