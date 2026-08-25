import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { IconInfoCircle } from '@tabler/icons-react'
import styles from './InfoHint.module.css'

const POPOVER_WIDTH = 300

export function InfoHint({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function place() {
      const rect = triggerRef.current?.getBoundingClientRect()
      if (!rect) return
      const margin = 8
      const left = Math.min(rect.left, window.innerWidth - POPOVER_WIDTH - margin)
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
      if (triggerRef.current?.contains(target) || popoverRef.current?.contains(target)) return
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

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={styles['info-hint-trigger']}
        aria-label="Пояснение"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setOpen((v) => !v)
        }}
      >
        <IconInfoCircle size={13} stroke={1.8} />
      </button>

      {open &&
        pos &&
        createPortal(
          <div
            ref={popoverRef}
            role="tooltip"
            className={styles['info-hint-popover']}
            style={{ top: pos.top, left: pos.left, width: POPOVER_WIDTH }}
            onClick={(e) => e.stopPropagation()}
          >
            {text}
          </div>,
          document.body,
        )}
    </>
  )
}
