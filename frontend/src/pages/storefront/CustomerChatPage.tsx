import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useParams } from 'react-router-dom'
import { IconChevronLeft, IconSend } from '@tabler/icons-react'
import {
  listCustomerChatMessages,
  loadCustomerToken,
  markCustomerChatSeen,
  sendCustomerChatMessage,
  type CustomerChatMessage,
} from '../../entities/auth/customerApi'
import { ApiError } from '../../shared/api/client'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { loadLastStoreSlug } from '../../shared/lib/lastStore'
import { IconButton } from '../../shared/ui/IconButton'
import styles from './Storefront.module.css'

/**
 * Чат по заявке из личного кабинета — доступ по JWT покупателя,
 * не по токену заявки.
 */
export function CustomerChatPage() {
  const { requestId: requestIdParam = '' } = useParams<{ requestId: string }>()
  const location = useLocation()
  const requestId = Number(requestIdParam)
  const token = loadCustomerToken()
  const [messages, setMessages] = useState<CustomerChatMessage[]>([])
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setPageMeta({ title: `Чат · заказ #${requestId}` })
    return () => resetPageMeta()
  }, [requestId])

  useEffect(() => {
    if (!token || !Number.isFinite(requestId)) {
      setLoading(false)
      return
    }
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const chat = await listCustomerChatMessages(requestId)
        if (cancelled) return
        setMessages(chat)
        const last = chat[chat.length - 1]
        markCustomerChatSeen(requestId, last?.created_at ?? new Date().toISOString())
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Не удалось загрузить чат')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [token, requestId])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages])

  if (!token) {
    const next = encodeURIComponent(location.pathname)
    const loginSlug = loadLastStoreSlug() || 'waysklad'
    return <Navigate to={`/store/${loginSlug}/login?next=${next}`} replace />
  }

  if (!Number.isFinite(requestId)) {
    return <Navigate to="/account/chats" replace />
  }

  async function handleSend(e: FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    setSending(true)
    setError(null)
    try {
      const msg = await sendCustomerChatMessage(requestId, text.trim())
      setMessages((prev) => (prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]))
      markCustomerChatSeen(requestId, msg.created_at ?? new Date().toISOString())
      setText('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось отправить')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className={styles.shell}>
      <header className={styles.headerCompact}>
        <Link to={"/account/chats"} className={styles.back}>
          <IconChevronLeft size={16} /> К чатам
        </Link>
      </header>

      <main className={styles.requestPage}>
        <h1>Чат · заказ #{requestId}</h1>
        {loading ? (
          <p className={styles.muted}>Загрузка…</p>
        ) : (
          <div className={styles.chat}>
            <div className={styles.chatList} ref={listRef}>
              {messages.length === 0 ? (
                <p className={styles.muted}>Напишите магазину, если нужно уточнить детали.</p>
              ) : (
                messages.map((m) => (
                  <div
                    key={m.id ?? `${m.author}-${m.created_at}-${m.text.slice(0, 12)}`}
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
              <IconButton
                type="submit"
                variant="accent"
                disabled={sending || !text.trim()}
                aria-label="Отправить"
              >
                <IconSend size={18} stroke={1.8} />
              </IconButton>
            </form>
          </div>
        )}
        {error && <p className={styles.error}>{error}</p>}
      </main>
    </div>
  )
}
