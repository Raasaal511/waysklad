import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  IconBuildingStore,
  IconCheck,
  IconX,
  IconSend,
  IconChevronLeft,
} from '@tabler/icons-react'
import {
  acceptStorefrontRequest,
  listNewStorefrontRequests,
  listStaffStorefrontChat,
  rejectStorefrontRequest,
  sendStaffStorefrontChat,
  type StorefrontMessage,
  type StorefrontRequest,
} from '../../entities/storefront/api'
import { useCatalog } from '../../app/CatalogContext'
import { useAuth } from '../../app/AuthContext'
import { ApiError } from '../../shared/api/client'
import { Button } from '../../shared/ui/Button'
import { DateInput } from '../../shared/ui/DateInput'
import { Modal } from '../../shared/ui/Modal'
import { Select } from '../../shared/ui/Select'
import { IconButton } from '../../shared/ui/IconButton'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './StorefrontRequestsPage.module.css'

export function StorefrontRequestsPage() {
  return (
    <div className={layoutStyles.stack}>
      <Link to="/storefront?tab=requests" className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> Витрина
      </Link>
      <StorefrontRequestsPanel />
    </div>
  )
}

export function StorefrontRequestsPanel({ embedded = false }: { embedded?: boolean }) {
  const { user } = useAuth()
  const canManage = user?.role === 'owner' || user?.role === 'manager' || user?.role === 'seller'
  const { products, warehouses, ensureProducts, ensureWarehouses } = useCatalog()
  const [requests, setRequests] = useState<StorefrontRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [accepting, setAccepting] = useState<StorefrontRequest | null>(null)
  const [chatRequest, setChatRequest] = useState<StorefrontRequest | null>(null)

  async function reload() {
    setLoading(true)
    setError(null)
    try {
      const list = await listNewStorefrontRequests()
      setRequests(list)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить заявки')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    ensureProducts().catch(() => {})
    ensureWarehouses().catch(() => {})
    reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const productName = (id: number) => products.find((p) => p.id === id)?.name ?? `Товар #${id}`

  async function handleReject(req: StorefrontRequest) {
    try {
      await rejectStorefrontRequest(req.id)
      setRequests((prev) => prev.filter((r) => r.id !== req.id))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось отклонить')
    }
  }

  return (
    <div className={layoutStyles.stack}>
      {!embedded && (
        <div className={layoutStyles.sectionTitle}>
          <div className={layoutStyles.row} style={{ gap: 8 }}>
            <IconBuildingStore size={22} stroke={1.8} />
            <h2>Заявки с витрины</h2>
            {requests.length > 0 && (
              <span className={layoutStyles.countBadge}>{requests.length}</span>
            )}
          </div>
        </div>
      )}

      {embedded && requests.length > 0 && (
        <p className={layoutStyles.textMuted}>Новых заявок: {requests.length}</p>
      )}

      <p className={layoutStyles.textMuted}>
        Покупатели оставляют заявки на публичной витрине. Примите — и создастся заказ с резервом
        на выбранном складе.
      </p>

      {error && <p className={layoutStyles.error}>{error}</p>}
      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : requests.length === 0 ? (
        <p className={layoutStyles.textMuted}>Новых заявок нет</p>
      ) : (
        <div className={styles.list}>
          {requests.map((req) => (
            <article key={req.id} className={styles.card}>
              <div className={styles.cardHead}>
                <div>
                  <strong>{req.customer_name}</strong>
                  {req.customer_phone && (
                    <span className={layoutStyles.textMuted}> · {req.customer_phone}</span>
                  )}
                </div>
                <span className="badge accent">Новая</span>
              </div>
              {req.note && <p className={styles.note}>{req.note}</p>}
              <ul className={styles.lines}>
                {req.lines.map((line, i) => (
                  <li key={`${line.product_id}-${i}`}>
                    {productName(line.product_id)} × {line.quantity}
                  </li>
                ))}
              </ul>
              <div className={styles.actions}>
                <Button variant="secondary" onClick={() => setChatRequest(req)}>
                  Чат
                </Button>
                {canManage && (
                  <>
                    <Button onClick={() => setAccepting(req)}>
                      <IconCheck size={16} stroke={1.8} /> Принять
                    </Button>
                    <Button variant="danger" onClick={() => handleReject(req)}>
                      <IconX size={16} stroke={1.8} /> Отклонить
                    </Button>
                  </>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {accepting && (
        <AcceptModal
          request={accepting}
          warehouses={warehouses}
          onClose={() => setAccepting(null)}
          onDone={() => {
            setRequests((prev) => prev.filter((r) => r.id !== accepting.id))
            setAccepting(null)
          }}
        />
      )}

      {chatRequest && (
        <StaffChatModal request={chatRequest} onClose={() => setChatRequest(null)} />
      )}
    </div>
  )
}

function AcceptModal({
  request,
  warehouses,
  onClose,
  onDone,
}: {
  request: StorefrontRequest
  warehouses: { id: number; name: string }[]
  onClose: () => void
  onDone: () => void
}) {
  const [warehouseId, setWarehouseId] = useState(warehouses[0]?.id ?? 0)
  const [dueDate, setDueDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [prepayment, setPrepayment] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await acceptStorefrontRequest(request.id, {
        warehouse_id: warehouseId,
        due_date: dueDate,
        prepayment: prepayment || undefined,
      })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось принять заявку')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={`Принять заявку · ${request.customer_name}`} onClose={onClose}>
      <form className={layoutStyles.form} onSubmit={handleSubmit}>
        <label className={layoutStyles.field}>
          Склад
          <Select
            value={String(warehouseId)}
            onChange={(v) => setWarehouseId(Number(v))}
            options={warehouses.map((w) => ({ value: String(w.id), label: w.name }))}
          />
        </label>
        <label className={layoutStyles.field}>
          Дата готовности
          <DateInput value={dueDate} min={new Date().toISOString().slice(0, 10)} onChange={setDueDate} />
        </label>
        <label className={layoutStyles.field}>
          Предоплата (необязательно)
          <input
            type="text"
            inputMode="decimal"
            value={prepayment}
            onChange={(e) => setPrepayment(e.target.value)}
            placeholder="0"
          />
        </label>
        {error && <p className={layoutStyles.error}>{error}</p>}
        <Button type="submit" disabled={saving || !warehouseId}>
          {saving ? 'Сохранение…' : 'Принять и создать заказ'}
        </Button>
      </form>
    </Modal>
  )
}

function StaffChatModal({
  request,
  onClose,
}: {
  request: StorefrontRequest
  onClose: () => void
}) {
  const [messages, setMessages] = useState<StorefrontMessage[]>([])
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    listStaffStorefrontChat(request.id)
      .then((msgs) => {
        if (!cancelled) setMessages(msgs)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Не удалось загрузить чат')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [request.id])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages])

  async function handleSend(e: FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    setSending(true)
    setError(null)
    try {
      const msg = await sendStaffStorefrontChat(request.id, text.trim())
      setMessages((prev) => [...prev, msg])
      setText('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось отправить')
    } finally {
      setSending(false)
    }
  }

  return (
    <Modal title={`Чат · ${request.customer_name}`} onClose={onClose} size="wide">
      <div className={styles.chatWrap}>
        {loading ? (
          <p className={layoutStyles.textMuted}>Загрузка…</p>
        ) : (
          <div className={styles.chatList} ref={listRef}>
            {messages.length === 0 ? (
              <p className={layoutStyles.textMuted}>Сообщений пока нет</p>
            ) : (
              messages.map((m) => (
                <div
                  key={m.id}
                  className={m.author === 'staff' ? styles.bubbleMine : styles.bubbleTheirs}
                >
                  <p>{m.text}</p>
                </div>
              ))
            )}
          </div>
        )}
        <form className={styles.chatForm} onSubmit={handleSend}>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Ответ покупателю…"
            maxLength={2000}
          />
          <IconButton type="submit" variant="accent" disabled={sending || !text.trim()} aria-label="Отправить">
            <IconSend size={18} stroke={1.8} />
          </IconButton>
        </form>
        {error && <p className={layoutStyles.error}>{error}</p>}
      </div>
    </Modal>
  )
}
