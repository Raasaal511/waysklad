import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { IconChevronLeft, IconSend } from '@tabler/icons-react'
import {
  getStorefrontRequestStatus,
  listStorefrontChat,
  loadRequestToken,
  sendStorefrontChat,
  storefrontChatWsUrl,
  type StorefrontMessage,
  type StorefrontRequestStatusResponse,
} from '../../entities/storefront/api'
import { ApiError } from '../../shared/api/client'
import { formatMoney } from '../../shared/lib/format'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import styles from './Storefront.module.css'

const STATUS_LABELS: Record<string, string> = {
  new: 'Ожидает ответа магазина',
  accepted: 'Принята — оформлен заказ',
  rejected: 'Отклонена',
}

const ORDER_STATUS_LABELS: Record<string, string> = {
  new: 'Новый',
  in_progress: 'В работе',
  ready: 'Готов',
  issued: 'Выдан',
  cancelled: 'Отменён',
}

export function StorefrontRequestPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const token = loadRequestToken(slug)
  const [status, setStatus] = useState<StorefrontRequestStatusResponse | null>(null)
  const [messages, setMessages] = useState<StorefrontMessage[]>([])
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!token) {
      setLoading(false)
      return
    }
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const [st, chat] = await Promise.all([
          getStorefrontRequestStatus(token!),
          listStorefrontChat(token!),
        ])
        if (cancelled) return
        setStatus(st)
        setMessages(chat)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Не удалось загрузить заявку')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [token])

  useEffect(() => {
    if (!token) return
    let ws: WebSocket | null = null
    let closed = false
    let retryTimer: number | undefined

    function connect() {
      if (closed) return
      ws = new WebSocket(storefrontChatWsUrl(token!))
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data as string) as StorefrontMessage
          setMessages((prev) => (prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]))
        } catch {
          // ignore
        }
      }
      ws.onclose = () => {
        if (!closed) retryTimer = window.setTimeout(connect, 3000)
      }
    }
    connect()
    return () => {
      closed = true
      if (retryTimer) window.clearTimeout(retryTimer)
      ws?.close()
    }
  }, [token])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages])

  async function handleSend(e: FormEvent) {
    e.preventDefault()
    if (!token || !text.trim()) return
    setSending(true)
    setError(null)
    try {
      const msg = await sendStorefrontChat(token, text.trim())
      setMessages((prev) => (prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]))
      setText('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось отправить')
    } finally {
      setSending(false)
    }
  }

  if (!token) {
    return (
      <div className={styles.shell}>
        <div className={styles.emptyState}>
          <h1>Заявка не найдена</h1>
          <p>Оформите заявку из корзины — ссылка сохранится на этом устройстве.</p>
          <Link to={`/store/${slug}`}>
            <Button>К витрине</Button>
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.shell}>
      <header className={styles.headerCompact}>
        <Link to={`/store/${slug}`} className={styles.back}>
          <IconChevronLeft size={16} /> К каталогу
        </Link>
      </header>

      <main className={styles.requestPage}>
        <h1>Ваша заявка</h1>
        {loading ? (
          <p className={styles.muted}>Загрузка…</p>
        ) : (
          <>
            {status && (
              <div className={styles.statusCard}>
                <strong>{STATUS_LABELS[status.status] ?? status.status}</strong>
                {status.order && (
                  <div className={styles.statusDetails}>
                    <span>Готовность: {new Date(status.order.due_date).toLocaleDateString('ru-RU')}</span>
                    <span>Сумма: {formatMoney(status.order.total)} ₽</span>
                    <span>К доплате: {formatMoney(status.order.to_pay)} ₽</span>
                    <span>
                      Статус заказа:{' '}
                      {ORDER_STATUS_LABELS[status.order.status] ?? status.order.status}
                    </span>
                  </div>
                )}
              </div>
            )}

            <div className={styles.chat}>
              <h2>Переписка с магазином</h2>
              <div className={styles.chatList} ref={listRef}>
                {messages.length === 0 ? (
                  <p className={styles.muted}>Напишите магазину, если нужно уточнить детали.</p>
                ) : (
                  messages.map((m) => (
                    <div
                      key={m.id}
                      className={m.author === 'customer' ? styles.bubbleMine : styles.bubbleStaff}
                    >
                      <p>{m.text}</p>
                      {m.created_at && (
                        <time>
                          {new Date(m.created_at).toLocaleString('ru-RU', {
                            day: '2-digit',
                            month: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </time>
                      )}
                    </div>
                  ))
                )}
              </div>
              <form className={styles.chatForm} onSubmit={handleSend}>
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Сообщение…"
                  maxLength={2000}
                />
                <IconButton type="submit" variant="accent" disabled={sending || !text.trim()} aria-label="Отправить">
                  <IconSend size={18} stroke={1.8} />
                </IconButton>
              </form>
            </div>
          </>
        )}
        {error && <p className={styles.error}>{error}</p>}
      </main>
    </div>
  )
}
