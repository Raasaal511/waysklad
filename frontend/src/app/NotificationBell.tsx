import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { IconBell } from '@tabler/icons-react'
import {
  listNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  notificationsWsUrl,
  type Notification,
} from '../entities/notification/api'
import layoutStyles from '../shared/ui/Layout.module.css'
import styles from './NotificationBell.module.css'

const POLL_INTERVAL_MS = 60_000

function formatTime(value: string | null) {
  if (!value) return ''
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getAccessToken(): string | null {
  return localStorage.getItem('access_token') ?? sessionStorage.getItem('access_token')
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

    function refresh() {
      if (document.visibilityState !== 'visible') return
      listNotifications()
        .then((r) => {
          if (cancelled) return
          setItems(r.items)
          setUnread(r.unread)
        })
        .catch(() => {})
    }

    refresh()
    const pollId = window.setInterval(refresh, POLL_INTERVAL_MS)

    let ws: WebSocket | null = null
    let retryTimer: number | undefined
    let closed = false

    function connectWs() {
      const token = getAccessToken()
      if (!token || closed) return
      ws = new WebSocket(notificationsWsUrl(token))
      ws.onmessage = (ev) => {
        try {
          const n = JSON.parse(ev.data as string) as Notification
          setItems((prev) => (prev.some((x) => x.id === n.id) ? prev : [{ ...n, is_read: false }, ...prev]))
          setUnread((prev) => prev + 1)
        } catch {
          // ignore malformed
        }
      }
      ws.onclose = () => {
        if (!closed) {
          refresh()
          retryTimer = window.setTimeout(connectWs, 4000)
        }
      }
    }
    connectWs()

    function onVisible() {
      if (document.visibilityState === 'visible') refresh()
    }
    document.addEventListener('visibilitychange', onVisible)

    return () => {
      cancelled = true
      closed = true
      window.clearInterval(pollId)
      if (retryTimer) window.clearTimeout(retryTimer)
      document.removeEventListener('visibilitychange', onVisible)
      ws?.close()
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
        <IconBell size={24} stroke={1.8} />
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
