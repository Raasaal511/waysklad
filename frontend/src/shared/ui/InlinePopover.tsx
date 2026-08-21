import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

const POPOVER_WIDTH = 280

/** Компактная всплывающая панель у кнопки-триггера — замена модалке-поверх-модалки
 * для быстрых мини-форм ("+ новая категория" рядом с select и т.п). */
export function InlinePopover({
  title,
  trigger,
  open,
  onOpenChange,
  children,
}: {
  title: string
  trigger: ReactNode
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}) {
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)
  const anchorRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    if (!open) return
    function place() {
      const rect = anchorRef.current?.getBoundingClientRect()
      if (!rect) return
      const margin = 12
      const left = Math.min(
        Math.max(rect.right - POPOVER_WIDTH, margin),
        window.innerWidth - POPOVER_WIDTH - margin,
      )
      setPos({ top: rect.bottom + 6, left })
    }
    place()
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => {
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node
      if (anchorRef.current?.contains(target) || panelRef.current?.contains(target)) return
      onOpenChange(false)
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onOpenChange(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open, onOpenChange])

  return (
    <div ref={anchorRef} className="inline-popover-anchor">
      {trigger}
      {open &&
        pos &&
        createPortal(
          <div
            ref={panelRef}
            role="dialog"
            aria-label={title}
            className="inline-popover"
            style={{ top: pos.top, left: pos.left, width: POPOVER_WIDTH }}
          >
            <div className="inline-popover-title">{title}</div>
            {children}
          </div>,
          document.body,
        )}
    </div>
  )
}
