import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import styles from './InlinePopover.module.css'

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
      // .inline-popover-anchor рендерится с display:contents (чтобы не мешать
      // flex/grid-раскладке родителя), а у таких элементов нет своего бокса —
      // getBoundingClientRect() на самом anchor всегда вернёт нулевой прямоугольник.
      // Поэтому меряем реальный DOM-узел триггера (его первый дочерний элемент).
      const rect = anchorRef.current?.firstElementChild?.getBoundingClientRect()
      if (!rect) return
      // триггер полностью ушёл за пределы окна (проскроллили мимо) — закрываем панель,
      // а не тащим её вникуда за кнопкой
      if (rect.bottom < 0 || rect.top > window.innerHeight) {
        onOpenChange(false)
        return
      }
      const margin = 12
      const offsetX = 20
      const offsetY = 40
      const left = Math.min(
        Math.max(rect.left + offsetX, margin),
        window.innerWidth - POPOVER_WIDTH - margin,
      )
      // размер панели фиксирован (не сжимаем и не переворачиваем) — если снизу не
      // хватает места в границах модалки, просто поднимаем панель выше, чтобы она
      // целиком вошла над футером
      const dialog = anchorRef.current?.closest('[role="dialog"]')
      const dialogRect = dialog?.getBoundingClientRect()
      const footer = dialog?.querySelector('[class*="modal-footer"]')
      const boundary = footer ? footer.getBoundingClientRect().top : (dialogRect ? dialogRect.bottom : window.innerHeight)
      const panelHeight = panelRef.current?.offsetHeight ?? 0
      const top = Math.max(margin, Math.min(rect.bottom + offsetY, boundary - panelHeight - margin))
      setPos({ top, left })
    }
    place()
    // после первого прохода панель ещё не была в DOM, и её реальная высота
    // не учтена (panelHeight=0) — пересчитываем на следующем кадре, когда она уже отрендерена
    const raf = requestAnimationFrame(place)
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  }, [open, onOpenChange])

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
    <div ref={anchorRef} className={styles['inline-popover-anchor']}>
      {trigger}
      {open &&
        pos &&
        createPortal(
          <div
            ref={panelRef}
            role="dialog"
            aria-label={title}
            className={styles['inline-popover']}
            style={{ top: pos.top, left: pos.left, width: POPOVER_WIDTH }}
          >
            <div className={styles['inline-popover-title']}>{title}</div>
            {children}
          </div>,
          document.body,
        )}
    </div>
  )
}
