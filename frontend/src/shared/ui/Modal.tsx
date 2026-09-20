import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { IconX } from '@tabler/icons-react'
import { IconButton } from './IconButton'
import styles from './Modal.module.css'

// Счётчик открытых модалок — блокируем скролл фона на первой и снимаем блокировку
// только когда закрылась последняя (модалки бывают вложенные, см. OrderDetail).
// Просто overflow:hidden на body не держит iOS Safari от прокрутки фона свайпом,
// поэтому дополнительно "замораживаем" body через position:fixed с сохранением scrollY.
let modalLockCount = 0
let savedScrollY = 0

function lockBodyScroll() {
  if (modalLockCount === 0) {
    savedScrollY = window.scrollY
    const body = document.body
    body.style.position = 'fixed'
    body.style.top = `-${savedScrollY}px`
    body.style.left = '0'
    body.style.right = '0'
    body.style.overflow = 'hidden'
  }
  modalLockCount++
}

function unlockBodyScroll() {
  modalLockCount = Math.max(0, modalLockCount - 1)
  if (modalLockCount === 0) {
    const body = document.body
    body.style.position = ''
    body.style.top = ''
    body.style.left = ''
    body.style.right = ''
    body.style.overflow = ''
    window.scrollTo(0, savedScrollY)
  }
}

interface ModalProps {
  title: ReactNode
  onClose: () => void
  children: ReactNode
  wide?: boolean
  size?: 'wide' | 'full'
  footer?: ReactNode
  headerActions?: ReactNode
}

export function Modal({ title, onClose, children, wide, size, footer, headerActions }: ModalProps) {
  const effectiveSize = size ?? (wide ? 'wide' : undefined)
  const titleId = useId()
  const bodyRef = useRef<HTMLDivElement>(null)
  const [atBottom, setAtBottom] = useState(true)
  // Фокус должен вернуться на кнопку, которая открыла модалку (см. Lightbox — тот же паттерн),
  // иначе после Esc/крестика фокус улетает на <body> и клавиатурная навигация теряется (блок «Д» п.11).
  const previouslyFocused = useRef<HTMLElement | null>(null)

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    previouslyFocused.current = document.activeElement as HTMLElement
    document.addEventListener('keydown', handleKey)
    lockBodyScroll()
    return () => {
      document.removeEventListener('keydown', handleKey)
      unlockBodyScroll()
      previouslyFocused.current?.focus?.()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    <div className={styles['modal-overlay']} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        className={[styles.modal, effectiveSize ? styles[`modal-${effectiveSize}`] : '']
          .filter(Boolean)
          .join(' ')}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className={styles['modal-header']}>
          <h3 id={titleId}>{title}</h3>
          <div className={styles['modal-header-actions']}>
            {headerActions}
            <IconButton
              variant="neutral"
              size="lg"
              className={styles['modal-close']}
              onClick={onClose}
              aria-label="Закрыть"
            >
              <IconX size={22} stroke={1.8} />
            </IconButton>
          </div>
        </div>
        <div className={styles['modal-body']} ref={bodyRef}>
          {children}
        </div>
        {footer && (
          <div
            className={[styles['modal-footer'], atBottom ? styles['modal-footer-flush'] : '']
              .filter(Boolean)
              .join(' ')}
          >
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}
