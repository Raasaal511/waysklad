import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Icon } from './icons/Icon'
import { IconButton } from './IconButton'

interface ModalProps {
  title: string
  onClose: () => void
  children: ReactNode
  wide?: boolean
  size?: 'wide' | 'full'
  footer?: ReactNode
}

export function Modal({ title, onClose, children, wide, size, footer }: ModalProps) {
  const effectiveSize = size ?? (wide ? 'wide' : undefined)
  const bodyRef = useRef<HTMLDivElement>(null)
  const [atBottom, setAtBottom] = useState(true)

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', handleKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  useEffect(() => {
    if (!footer) return
    const el = bodyRef.current
    if (!el) return

    function checkScroll() {
      if (!el) return
      setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 4)
    }

    checkScroll()
    el.addEventListener('scroll', checkScroll)
    const observer = new ResizeObserver(checkScroll)
    observer.observe(el)
    return () => {
      el.removeEventListener('scroll', checkScroll)
      observer.disconnect()
    }
  }, [footer, children])

  return createPortal(
    <div className="modal-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        className={`modal${effectiveSize ? ` modal-${effectiveSize}` : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="modal-header">
          <h3>{title}</h3>
          <IconButton variant="muted" className="modal-close" onClick={onClose} aria-label="Закрыть">
            <Icon name="close" size={18} />
          </IconButton>
        </div>
        <div className="modal-body" ref={bodyRef}>
          {children}
        </div>
        {footer && (
          <div className={`modal-footer${atBottom ? ' modal-footer-flush' : ''}`}>{footer}</div>
        )}
      </div>
    </div>,
    document.body,
  )
}
