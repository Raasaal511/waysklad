import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { IconBell } from '@tabler/icons-react'
import {
  listNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  type Notification,
} from '../entities/notification/api'
import layoutStyles from '../shared/ui/Layout.module.css'
import styles from './NotificationBell.module.css'

const POLL_INTERVAL_MS = 30_000

function formatTime(value: string | null) {
  if (!value) return ''
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function NotificationBell({ align = 'right' }: { align?: 'left' | 'right' }) {
  const [items, setItems] = useState<Notification[]>([])
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    let cancelled = false
    function tick() {
      if (document.visibilityState !== 'visible') return
      listNotifications()
        .then((r) => {
          if (cancelled) return
          setItems(r.items)
          setUnread(r.unread)
        })
        .catch(() => {})
    }
    tick()
    const id = window.setInterval(tick, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [])

  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node
      if (triggerRef.current?.contains(target) || panelRef.current?.contains(target)) return
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

  async function handleItemClick(n: Notification) {
    setOpen(false)
    if (!n.is_read) {
      markNotificationRead(n.id).catch(() => {})
      setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)))
      setUnread((prev) => Math.max(0, prev - 1))
    }
    navigate(n.link || '/tasks')
  }

  async function handleReadAll() {
    try {
      await markAllNotificationsRead()
      setItems((prev) => prev.map((x) => ({ ...x, is_read: true })))
      setUnread(0)
    } catch {
      // тихо игнорируем — колокольчик обновится на следующем опросе
    }
  }

  return (
    <div ref={triggerRef} className={styles['app-bell']}>
      <button
        type="button"
        className={styles['app-bell-trigger']}
        aria-label="Уведомления"
        onClick={() => setOpen((v) => !v)}
      >
        <IconBell size={19} stroke={1.8} />
        {unread > 0 && <span className={styles['app-bell-badge']}>{unread > 9 ? '9+' : unread}</span>}
      </button>

      {open && (
        <div
          ref={panelRef}
          className={[styles['app-bell-panel'], align === 'left' && styles['app-bell-panel-left']]
            .filter(Boolean)
            .join(' ')}
        >
          <div className={styles['app-bell-panel-header']}>
            <span>Уведомления</span>
            {unread > 0 && (
              <button type="button" className={styles['app-bell-read-all']} onClick={handleReadAll}>
                Прочитать все
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <p className={[layoutStyles.textMuted, styles['app-bell-empty']].join(' ')}>Пока пусто</p>
          ) : (
            <div className={styles['app-bell-list']}>
              {items.map((n) => (
                <button
                  key={n.id}
                  type="button"
                  className={[styles['app-bell-item'], !n.is_read && styles['app-bell-item-unread']]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => handleItemClick(n)}
                >
                  <span className={styles['app-bell-item-text']}>{n.text}</span>
                  <span className={styles['app-bell-item-time']}>{formatTime(n.created_at)}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
