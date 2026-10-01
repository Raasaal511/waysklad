import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { IconCircleCheck, IconSend } from '@tabler/icons-react'
import { listMyStorefrontRequests, loadCustomerToken, type MyRequest } from '../../entities/auth/customerApi'
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
import { EmptyState } from '../../shared/ui/EmptyState'
import { IconButton } from '../../shared/ui/IconButton'
import { RequestSummary } from './RequestSummary'
import styles from './Storefront.module.css'
import pageStyles from './StorefrontRequestPage.module.css'

const STATUS_LABELS: Record<string, string> = {
  new: 'Ждёт ответа магазина',
  accepted: 'Магазин подтвердил',
  rejected: 'Отклонён',
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
  const location = useLocation()
  const navigate = useNavigate()
  const navState = location.state as { insufficientStock?: boolean; requestId?: number } | null
  const insufficientFromSubmit = navState?.insufficientStock === true
  // пришли из корзины сразу после отправки, а не открыли заказ позже
  const justSent = navState?.requestId != null
  const [myRequest, setMyRequest] = useState<MyRequest | null>(null)
  const token = loadRequestToken(slug)
  const [status, setStatus] = useState<StorefrontRequestStatusResponse | null>(null)
  const [messages, setMessages] = useState<StorefrontMessage[]>([])
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showStockWarning] = useState(insufficientFromSubmit)
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
        // Состав заказа — из «Моих заказов» покупателя (status по токену его не отдаёт)
        if (navState?.requestId != null && loadCustomerToken()) {
          const mine = await listMyStorefrontRequests({ limit: 20 }).catch(() => null)
          // только точно известный заказ: «последний в этом магазине» мог оказаться
          // другим (заказ из Telegram-бота, с другого устройства) — со своим чатом
          const found = mine?.items.find((r) => r.id === navState?.requestId) ?? null
          if (!cancelled) setMyRequest(found)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Не удалось загрузить заказ')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      <main className={pageStyles.page}>
        <EmptyState
          illustration="empty-box"
          title="Заказ не найден"
          description="Ваши заказы — в профиле, вкладка «Заказы»."
          actionLabel="Мои заказы"
          onAction={() => navigate('/account/orders')}
        />
      </main>
    )
  }

  const statusLabel = status ? (STATUS_LABELS[status.status] ?? status.status) : null

  return (
    <main className={pageStyles.page}>
      <section className={pageStyles.hero}>
        <span className={pageStyles.heroIcon} aria-hidden="true">
          <IconCircleCheck size={32} stroke={1.8} />
        </span>
        <div className={pageStyles.heroText}>
          <h1 className={pageStyles.title}>
            {justSent ? 'Заказ отправлен' : 'Ваш заказ'}
            {myRequest && <span className={pageStyles.number}> №{myRequest.id}</span>}
          </h1>
          {statusLabel && (
            <span className={pageStyles.status} data-status={status?.status}>
              {statusLabel}
            </span>
          )}
        </div>
      </section>

      {status?.status === 'new' && (
        <ol className={pageStyles.steps}>
          <li>Магазин проверит наличие и подтвердит заказ</li>
          <li>Ответ придёт сюда, в чат, и в профиль → Заказы</li>
          <li>Забираете и платите при получении</li>
        </ol>
      )}

      {showStockWarning && (
        <p className={pageStyles.warning}>
          Часть товара могли уже разобрать — магазин уточнит наличие и напишет вам.
        </p>
      )}

      {loading ? (
        <p className={pageStyles.muted}>Загрузка…</p>
      ) : (
        <>
          {myRequest && (
            <section className={pageStyles.card}>
              <h2 className={pageStyles.cardTitle}>Состав заказа</h2>
              <RequestSummary req={myRequest} />
            </section>
          )}

          {!myRequest && status?.order && (
            <section className={pageStyles.card}>
              <p className={pageStyles.muted}>
                Готовность: {new Date(status.order.due_date).toLocaleDateString('ru-RU')} · сумма{' '}
                {formatMoney(status.order.total)} ₽ · к доплате {formatMoney(status.order.to_pay)} ₽ ·{' '}
                {ORDER_STATUS_LABELS[status.order.status] ?? status.order.status}
              </p>
            </section>
          )}

          <section className={pageStyles.card}>
            <h2 className={pageStyles.cardTitle}>Чат с магазином</h2>
            <div className={styles.chatList} ref={listRef}>
              {messages.length === 0 ? (
                <p className={pageStyles.muted}>Нужно что-то уточнить — напишите, магазин ответит здесь.</p>
              ) : (
                messages.map((m) => (
                  <div key={m.id} className={m.author === 'customer' ? styles.bubbleMine : styles.bubbleStaff}>
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
                placeholder="Сообщение магазину"
                aria-label="Сообщение магазину"
                maxLength={2000}
              />
              <IconButton
                type="submit"
                variant="accent"
                size="lg"
                disabled={sending || !text.trim()}
                aria-label="Отправить"
              >
                <IconSend size={20} stroke={1.8} />
              </IconButton>
            </form>
          </section>
        </>
      )}

      {error && (
        <p className={pageStyles.error} role="alert">
          {error}
        </p>
      )}

      <div className={pageStyles.actions}>
        <Button variant="secondary" onClick={() => navigate('/account/orders')}>
          Мои заказы
        </Button>
        <Button onClick={() => navigate(`/store/${slug}`)}>Продолжить покупки</Button>
      </div>
    </main>
  )
}
