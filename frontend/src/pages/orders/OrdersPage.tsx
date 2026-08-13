import { useEffect, useState, type FormEvent } from 'react'
import {
  listActiveOrders,
  createOrder,
  changeOrderStatus,
  type Order,
  type OrderStatus,
} from '../../entities/order/api'
import { listAllProducts, type Product } from '../../entities/product/api'
import { searchClients, type Client } from '../../entities/counterparty/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { IconPlus } from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
import { normalizeDecimalInput } from '../../shared/lib/format'

const STATUS_LABELS: Record<OrderStatus, string> = {
  new: 'Новый',
  in_progress: 'В работе',
  ready: 'Готов',
  issued: 'Выдан',
}

const NEXT_STATUS: Record<OrderStatus, OrderStatus | null> = {
  new: 'in_progress',
  in_progress: 'ready',
  ready: 'issued',
  issued: null,
}

export function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [products, setProducts] = useState<Product[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [o, p, c] = await Promise.all([listActiveOrders(), listAllProducts(), searchClients()])
      setOrders(o)
      setProducts(p)
      setClients(c)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить заказы')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const clientName = (id: number) => clients.find((c) => c.id === id)?.name ?? `#${id}`

  async function advance(order: Order) {
    const next = NEXT_STATUS[order.status]
    if (!next) return
    try {
      await changeOrderStatus(order.id, next)
      load()
    } catch {
      // статус не поменяется, пользователь увидит прежнее состояние
    }
  }

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Заказы</h2>
        <Button onClick={() => setShowForm(true)}>
          <IconPlus size={16} stroke={1.8} /> Заказ
        </Button>
      </div>

      {showForm && (
        <Modal title="Новый заказ" onClose={() => setShowForm(false)}>
          <NewOrderForm
            products={products}
            clients={clients}
            onDone={() => {
              setShowForm(false)
              load()
            }}
          />
        </Modal>
      )}

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : orders.length === 0 ? (
        <p className="text-muted">Активных заказов нет</p>
      ) : (
        <div className="stack">
          {orders.map((o) => (
            <div key={o.id} className="card card-full row between">
              <div className="stat">
                <span>
                  Заказ №{o.id} — {clientName(o.client_id)}
                </span>
                <span className="text-muted">
                  {o.total} ₽ · доплата {o.to_pay} ₽{o.due_date ? ` · до ${o.due_date}` : ''}
                </span>
              </div>
              <div className="row">
                <span className="badge accent">{STATUS_LABELS[o.status]}</span>
                {NEXT_STATUS[o.status] && (
                  <Button variant="secondary" onClick={() => advance(o)}>
                    → {STATUS_LABELS[NEXT_STATUS[o.status]!]}
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function NewOrderForm({
  products,
  clients,
  onDone,
}: {
  products: Product[]
  clients: Client[]
  onDone: () => void
}) {
  const [clientId, setClientId] = useState<number | null>(clients[0]?.id ?? null)
  const [productId, setProductId] = useState<number | null>(products[0]?.id ?? null)
  const [quantity, setQuantity] = useState('1')
  const [price, setPrice] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [prepayment, setPrepayment] = useState('0')
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!clientId || !productId) return
    setError(null)
    setSaving(true)
    try {
      await createOrder({
        client_id: clientId,
        items: [{ product_id: productId, quantity, price }],
        due_date: dueDate || null,
        prepayment,
        note,
      })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать заказ')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="field">
        Клиент
        <Select
          value={clientId != null ? String(clientId) : ''}
          onChange={(v) => setClientId(Number(v))}
          options={clients.map((c) => ({ value: String(c.id), label: c.name }))}
        />
      </label>
      <label className="field">
        Товар
        <Select
          value={productId != null ? String(productId) : ''}
          onChange={(v) => setProductId(Number(v))}
          options={products.map((p) => ({ value: String(p.id), label: p.name }))}
        />
      </label>
      <div className="row">
        <label className="field" style={{ flex: 1 }}>
          Количество
          <input
            type="text"
            inputMode="decimal"
            value={quantity}
            onChange={(e) => {
              const normalized = normalizeDecimalInput(e.target.value)
              if (normalized !== null) setQuantity(normalized)
            }}
          />
        </label>
        <label className="field" style={{ flex: 1 }}>
          Цена
          <input
            type="text"
            inputMode="decimal"
            value={price}
            onChange={(e) => {
              const normalized = normalizeDecimalInput(e.target.value)
              if (normalized !== null) setPrice(normalized)
            }}
            required
          />
        </label>
      </div>
      <div className="row">
        <label className="field" style={{ flex: 1 }}>
          Дата готовности
          <DateInput value={dueDate} onChange={setDueDate} />
        </label>
        <label className="field" style={{ flex: 1 }}>
          Предоплата
          <input
            type="text"
            inputMode="decimal"
            value={prepayment}
            onChange={(e) => {
              const normalized = normalizeDecimalInput(e.target.value)
              if (normalized !== null) setPrepayment(normalized)
            }}
          />
        </label>
      </div>
      <label className="field">
        Заметка
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="из директа…" />
      </label>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving || !clientId || !productId}>
        {saving ? 'Сохранение…' : 'Создать заказ'}
      </Button>
    </form>
  )
}
