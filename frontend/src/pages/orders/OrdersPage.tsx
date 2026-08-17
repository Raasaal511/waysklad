import { lazy, Suspense, useEffect, useMemo, useState, type CSSProperties, type DragEvent, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  listActiveOrders,
  listCompletedOrders,
  createOrder,
  updateOrder,
  changeOrderStatus,
  cancelOrder,
  issueOrder,
  getOrderHistory,
  type Order,
  type OrderStatus,
  type OrderSource,
  type OrderFormInput,
  type OrderHistoryEntry,
  type IssueOrderResult,
} from '../../entities/order/api'
import {
  ORDER_STATUS_LABELS,
  ORDER_STATUS_BADGE_CLASS,
  NEXT_STATUS,
  BOARD_STATUSES,
  STATUS_ACCENT,
} from '../../entities/order/orderStatus'
import { listAllProducts, listUnits, getByBarcode, type Product, type Unit } from '../../entities/product/api'
import { searchClients, type Client } from '../../entities/counterparty/api'
import { listWarehouses, listStock, type Warehouse, type StockItem } from '../../entities/inventory/api'
import { getSale, type Sale, type PaymentMethod } from '../../entities/sale/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import {
  IconPlus,
  IconX,
  IconTrash,
  IconMessage2,
  IconReceipt2,
  IconArrowRight,
  IconClock,
  IconBarcode,
  IconChevronRight,
  IconChevronLeft,
  IconChevronDown,
  IconPencil,
  IconBan,
  IconCheck,
  IconUsers,
  IconPhone,
  IconBrandInstagram,
  IconBrandWhatsapp,
  IconMapPin,
  IconLayoutKanban,
  IconTable,
  IconList,
  IconCalendar,
  type Icon as TablerIcon,
} from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { StockWarningIcon } from '../../shared/ui/StockWarningIcon'
import {
  formatMoney,
  formatQuantity,
  normalizeDecimalInput,
  centsToMoney,
  isOutOfStock,
  isLowStock,
} from '../../shared/lib/format'
import { isBarcodeScannerSupported } from '../../entities/barcode/barcodeSupport'
import { useAuth } from '../../app/AuthContext'

const BarcodeScanner = lazy(() =>
  import('../../entities/barcode/BarcodeScanner').then((m) => ({ default: m.BarcodeScanner })),
)

const ONBOARDING_DISMISSED_KEY = 'orders_onboarding_dismissed'
const ORDER_LINES_COLUMNS = '2fr 1fr 1fr 1fr'

const ORDER_SOURCE_LABELS: Record<OrderSource, string> = {
  whatsapp: 'WhatsApp',
  instagram: 'Instagram',
  call: 'Звонок',
  in_person: 'Очно',
}

const ORDER_SOURCE_ICONS: Record<OrderSource, TablerIcon> = {
  whatsapp: IconBrandWhatsapp,
  instagram: IconBrandInstagram,
  call: IconPhone,
  in_person: IconMapPin,
}

const PAYMENT_LABELS: Record<PaymentMethod, string> = {
  cash: 'Наличные',
  transfer: 'Перевод',
  credit: 'В долг',
}

const PAYMENT_BADGE_CLASS: Record<PaymentMethod, string> = {
  cash: 'badge accent',
  transfer: 'badge',
  credit: 'badge danger',
}

const ORDER_HISTORY_ACTION_LABELS: Record<string, string> = {
  'order.create': 'Заказ создан',
  'order.update': 'Изменён состав заказа',
  'order.status': 'Изменён статус',
  'order.cancel': 'Заказ отменён',
  'order.issue': 'Заказ выдан',
}

const ORDER_HISTORY_ACTION_ICONS: Record<string, TablerIcon> = {
  'order.create': IconCheck,
  'order.update': IconPencil,
  'order.status': IconArrowRight,
  'order.cancel': IconBan,
  'order.issue': IconReceipt2,
}

type Tab = 'active' | 'completed'
type ViewMode = 'board' | 'table' | 'list' | 'calendar'

const VIEW_MODE_KEY = 'orders_view_mode'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string; icon: TablerIcon }[] = [
  { mode: 'board', label: 'Доска', icon: IconLayoutKanban },
  { mode: 'table', label: 'Таблица', icon: IconTable },
  { mode: 'list', label: 'Список', icon: IconList },
  { mode: 'calendar', label: 'Календарь', icon: IconCalendar },
]

function isViewMode(v: string | null): v is ViewMode {
  return v === 'board' || v === 'table' || v === 'list' || v === 'calendar'
}

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const MONTHS = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]

function toISODate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const ORDER_TABLE_COLUMNS = '90px 1.6fr 1fr 120px 110px 100px 28px'

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDueDate(value: string) {
  const date = new Date(value)
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function isOverdue(dueDate: string) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return new Date(dueDate) < today
}

function initials(name: string) {
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase()
}

export function OrdersPage() {
  const { user } = useAuth()
  const canManage = user?.role === 'owner' || user?.role === 'manager' || user?.role === 'seller'

  const [activeOrders, setActiveOrders] = useState<Order[]>([])
  const [completedOrders, setCompletedOrders] = useState<Order[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [units, setUnits] = useState<Unit[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [stock, setStock] = useState<StockItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [tab, setTab] = useState<Tab>('active')
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    const saved = localStorage.getItem(VIEW_MODE_KEY)
    return isViewMode(saved) ? saved : 'board'
  })
  const [showOnboarding, setShowOnboarding] = useState(
    () => localStorage.getItem(ONBOARDING_DISMISSED_KEY) !== '1',
  )
  const [draggedId, setDraggedId] = useState<number | null>(null)
  const [dragOverStatus, setDragOverStatus] = useState<OrderStatus | null>(null)
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null)
  const [issuingOrder, setIssuingOrder] = useState<Order | null>(null)

  useEffect(() => {
    localStorage.setItem(VIEW_MODE_KEY, viewMode)
  }, [viewMode])

  function dismissOnboarding() {
    setShowOnboarding(false)
    localStorage.setItem(ONBOARDING_DISMISSED_KEY, '1')
  }

  async function load(silent = false) {
    if (!silent) setLoading(true)
    try {
      const [active, completed, p, u, c, w, s] = await Promise.all([
        listActiveOrders(),
        listCompletedOrders(),
        listAllProducts(),
        listUnits(),
        searchClients(),
        listWarehouses(),
        listStock(),
      ])
      setActiveOrders(active)
      setCompletedOrders(completed)
      setProducts(p)
      setUnits(u)
      setClients(c)
      setWarehouses(w)
      setStock(s)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить заказы')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const clientName = (id: number) => clients.find((c) => c.id === id)?.name ?? `#${id}`

  async function moveTo(order: Order, newStatus: OrderStatus) {
    if (order.status === newStatus) return
    try {
      await changeOrderStatus(order.id, newStatus)
      load(true)
    } catch {
      load(true)
    }
  }

  function handleAdvance(order: Order) {
    const next = NEXT_STATUS[order.status]
    if (!next) return
    if (next === 'issued') {
      setIssuingOrder(order)
    } else {
      moveTo(order, next)
    }
  }

  function handleDragStart(order: Order) {
    setDraggedId(order.id)
  }

  function handleDragEnd() {
    setDraggedId(null)
    setDragOverStatus(null)
  }

  function handleColumnDragOver(e: DragEvent<HTMLDivElement>, status: OrderStatus) {
    e.preventDefault()
    if (dragOverStatus !== status) setDragOverStatus(status)
  }

  function handleColumnDrop(e: DragEvent<HTMLDivElement>, status: OrderStatus) {
    e.preventDefault()
    const order = activeOrders.find((o) => o.id === draggedId)
    setDraggedId(null)
    setDragOverStatus(null)
    if (order) moveTo(order, status)
  }

  const orders = tab === 'active' ? activeOrders : completedOrders

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Заказы</h2>
        {canManage && (
          <Button onClick={() => setShowForm(true)}>
            <IconPlus size={16} stroke={1.8} /> Заказ
          </Button>
        )}
      </div>

      {showOnboarding && (
        <div className="card card-full orders-intro">
          <IconButton
            variant="muted"
            className="orders-intro-close"
            tooltip="Понятно, больше не показывать"
            aria-label="Понятно, больше не показывать"
            onClick={dismissOnboarding}
          >
            <IconX size={16} stroke={1.8} />
          </IconButton>
          <div className="orders-intro-flow">
            <div className="orders-intro-step">
              <span className="orders-intro-icon">
                <IconMessage2 size={20} stroke={1.8} />
              </span>
              <div className="stack" style={{ gap: 2 }}>
                <strong>Заказ</strong>
                <span className="text-muted">Клиент попросил заранее — остаток резервируется на складе</span>
              </div>
            </div>
            <IconArrowRight size={18} stroke={1.8} className="orders-intro-arrow" />
            <div className="orders-intro-step">
              <span className="orders-intro-icon orders-intro-icon-accent">
                <IconReceipt2 size={20} stroke={1.8} />
              </span>
              <div className="stack" style={{ gap: 2 }}>
                <strong>Выдача</strong>
                <span className="text-muted">Клиент забрал и доплатил — товар списан, продажа оформлена сама</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {showForm && (
        <Modal title="Новый заказ" onClose={() => setShowForm(false)} size="full">
          <NewOrderForm
            products={products}
            units={units}
            clients={clients}
            warehouses={warehouses}
            stock={stock}
            onDone={() => {
              setShowForm(false)
              load(true)
            }}
          />
        </Modal>
      )}

      {issuingOrder && (
        <IssueOrderModal
          order={issuingOrder}
          onClose={() => setIssuingOrder(null)}
          onIssued={() => {
            setIssuingOrder(null)
            load(true)
          }}
        />
      )}

      {selectedOrder && (
        <OrderDetail
          initialOrder={selectedOrder}
          products={products}
          units={units}
          clients={clients}
          warehouses={warehouses}
          stock={stock}
          canManage={canManage}
          onClose={() => setSelectedOrder(null)}
          onChanged={() => load(true)}
        />
      )}

      <div className="row between wrap" style={{ gap: 10 }}>
        <div className="sale-period-tabs">
          <Button variant="secondary" active={tab === 'active'} onClick={() => setTab('active')}>
            Активные
            {activeOrders.length > 0 && <span className="count-badge">{activeOrders.length}</span>}
          </Button>
          <Button variant="secondary" active={tab === 'completed'} onClick={() => setTab('completed')}>
            Завершённые
            {completedOrders.length > 0 && <span className="count-badge">{completedOrders.length}</span>}
          </Button>
        </div>
        {tab === 'active' && (
          <div className="view-switcher" role="tablist" aria-label="Вид отображения">
            {VIEW_MODE_OPTIONS.map(({ mode, label, icon: Icon }) => (
              <Button
                key={mode}
                variant="secondary"
                active={viewMode === mode}
                onClick={() => setViewMode(mode)}
              >
                <Icon size={15} stroke={1.8} /> {label}
              </Button>
            ))}
          </div>
        )}
      </div>

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : tab === 'active' && viewMode === 'table' ? (
        <OrdersTableView orders={activeOrders} clientName={clientName} onSelect={setSelectedOrder} />
      ) : tab === 'active' && viewMode === 'list' ? (
        activeOrders.length === 0 ? (
          <p className="text-muted">Активных заказов пока нет</p>
        ) : (
          <div className="orders-history-list">
            {activeOrders.map((o) => (
              <OrderListRow
                key={o.id}
                order={o}
                clientName={clientName}
                canManage={canManage}
                onSelect={setSelectedOrder}
                onAdvance={handleAdvance}
              />
            ))}
          </div>
        )
      ) : tab === 'active' && viewMode === 'calendar' ? (
        <OrdersCalendarView orders={activeOrders} clientName={clientName} onSelect={setSelectedOrder} />
      ) : tab === 'active' ? (
        <div className="orders-board" style={{ '--board-cols': BOARD_STATUSES.length } as CSSProperties}>
          {BOARD_STATUSES.map((status) => {
            const columnOrders = activeOrders.filter((o) => o.status === status)
            return (
              <div
                key={status}
                className={`orders-board-column${dragOverStatus === status ? ' orders-board-column-over' : ''}`}
                style={{ '--col-accent': STATUS_ACCENT[status] } as CSSProperties}
                onDragOver={(e) => handleColumnDragOver(e, status)}
                onDragLeave={() => setDragOverStatus((s) => (s === status ? null : s))}
                onDrop={(e) => handleColumnDrop(e, status)}
              >
                <div className="orders-board-column-head">
                  <span>{ORDER_STATUS_LABELS[status]}</span>
                  <span className="orders-board-column-count">{columnOrders.length}</span>
                  {status === 'new' && canManage && (
                    <IconButton
                      variant="accent"
                      className="orders-board-column-add"
                      tooltip="Новый заказ"
                      aria-label="Новый заказ"
                      onClick={() => setShowForm(true)}
                    >
                      <IconPlus size={14} stroke={2} />
                    </IconButton>
                  )}
                </div>
                <div className="orders-board-column-body">
                  {columnOrders.length === 0 ? (
                    status === 'new' && canManage ? (
                      <button type="button" className="orders-board-empty orders-board-empty-action" onClick={() => setShowForm(true)}>
                        <IconPlus size={16} stroke={1.8} /> Создать заказ
                      </button>
                    ) : (
                      <div className="orders-board-empty">Пусто</div>
                    )
                  ) : (
                    columnOrders.map((o) => {
                      const overdue = o.due_date != null && isOverdue(o.due_date)
                      const name = clientName(o.client_id)
                      const SourceIcon = ORDER_SOURCE_ICONS[o.source]
                      const partiallyPrepaid = Number(o.prepayment) > 0 && Number(o.to_pay) > 0
                      return (
                        <div
                          key={o.id}
                          className={`orders-board-card${draggedId === o.id ? ' orders-board-card-dragging' : ''}`}
                          draggable={canManage}
                          onDragStart={() => handleDragStart(o)}
                          onDragEnd={handleDragEnd}
                          onClick={() => setSelectedOrder(o)}
                        >
                          <div className="orders-board-card-head">
                            <span className="orders-board-card-number">
                              №{o.number ?? o.id}{' '}
                              <SourceIcon size={13} stroke={1.8} className="text-muted" title={ORDER_SOURCE_LABELS[o.source]} />
                            </span>
                            <span className="orders-board-card-total">{formatMoney(o.total)} ₽</span>
                          </div>
                          <strong className="orders-board-card-client">{name}</strong>
                          <div className="orders-board-card-footer">
                            {o.due_date ? (
                              <span
                                className={`orders-board-card-due${overdue ? ' orders-board-card-due-overdue' : ''}`}
                              >
                                <IconClock size={13} stroke={1.8} /> {formatDueDate(o.due_date)}
                              </span>
                            ) : partiallyPrepaid ? (
                              <span className="badge warning">предоплата {formatMoney(o.prepayment)} ₽</span>
                            ) : (
                              <span />
                            )}
                            <span className="orders-board-card-avatar" title={name}>
                              {initials(name)}
                            </span>
                          </div>
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ) : orders.length === 0 ? (
        <p className="text-muted">Завершённых заказов пока нет</p>
      ) : (
        <div className="orders-history-list">
          {orders.map((o) => (
            <div key={o.id} className="card orders-history-card" onClick={() => setSelectedOrder(o)}>
              <div className="orders-history-card-main">
                <div className="orders-history-card-title">
                  <strong>№{o.number ?? o.id}</strong>
                  <span>{clientName(o.client_id)}</span>
                  <span className={ORDER_STATUS_BADGE_CLASS[o.status]}>{ORDER_STATUS_LABELS[o.status]}</span>
                </div>
                {o.created_at && (
                  <span className="text-muted">
                    {o.status === 'cancelled' ? 'Создан' : 'Выдан'} {formatDateTime(o.created_at)}
                  </span>
                )}
              </div>
              <div className="orders-history-card-money">
                <span className="orders-board-card-total">{formatMoney(o.total)} ₽</span>
                {o.status === 'issued' && Number(o.to_pay) > 0 && (
                  <span className="text-muted">доплата {formatMoney(o.to_pay)} ₽</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function OrdersTableView({
  orders,
  clientName,
  onSelect,
}: {
  orders: Order[]
  clientName: (id: number) => string
  onSelect: (order: Order) => void
}) {
  if (orders.length === 0) return <p className="text-muted">Активных заказов пока нет</p>
  return (
    <div className="data-table">
      <div className="data-table-head" style={{ gridTemplateColumns: ORDER_TABLE_COLUMNS }}>
        <span>№</span>
        <span>Клиент</span>
        <span>Источник</span>
        <span>Статус</span>
        <span>Сумма</span>
        <span>Срок</span>
        <span />
      </div>
      <div className="data-table-body">
        {orders.map((o, i) => {
          const SourceIcon = ORDER_SOURCE_ICONS[o.source]
          const overdue = o.due_date != null && isOverdue(o.due_date)
          return (
            <button
              key={o.id}
              type="button"
              className="data-row data-row-link sale-history-row-in"
              style={
                {
                  gridTemplateColumns: ORDER_TABLE_COLUMNS,
                  '--row-delay': `${Math.min(i, 12) * 25}ms`,
                } as CSSProperties
              }
              onClick={() => onSelect(o)}
            >
              <span className="data-row-name">№{o.number ?? o.id}</span>
              <span>{clientName(o.client_id)}</span>
              <span className="row text-muted" style={{ gap: 4 }}>
                <SourceIcon size={14} stroke={1.8} /> {ORDER_SOURCE_LABELS[o.source]}
              </span>
              <span className={ORDER_STATUS_BADGE_CLASS[o.status]}>{ORDER_STATUS_LABELS[o.status]}</span>
              <span>{formatMoney(o.total)} ₽</span>
              <span className={overdue ? 'orders-board-card-due-overdue' : 'text-muted'}>
                {o.due_date ? formatDueDate(o.due_date) : '—'}
              </span>
              <IconChevronRight size={16} stroke={1.8} className="data-row-chevron" />
            </button>
          )
        })}
      </div>
    </div>
  )
}

function OrderListRow({
  order,
  clientName,
  canManage,
  onSelect,
  onAdvance,
}: {
  order: Order
  clientName: (id: number) => string
  canManage: boolean
  onSelect: (order: Order) => void
  onAdvance: (order: Order) => void
}) {
  const next = NEXT_STATUS[order.status]
  const overdue = order.due_date != null && isOverdue(order.due_date)
  return (
    <div className="card orders-history-card" onClick={() => onSelect(order)}>
      <div className="orders-history-card-main">
        <div className="orders-history-card-title">
          <strong>№{order.number ?? order.id}</strong>
          <span>{clientName(order.client_id)}</span>
          <span className={ORDER_STATUS_BADGE_CLASS[order.status]}>{ORDER_STATUS_LABELS[order.status]}</span>
        </div>
        {order.due_date && (
          <span className={overdue ? 'orders-board-card-due-overdue' : 'text-muted'}>
            <IconClock size={13} stroke={1.8} /> до {formatDueDate(order.due_date)}
          </span>
        )}
      </div>
      <div className="row" style={{ gap: 10 }}>
        <div className="orders-history-card-money">
          <span className="orders-board-card-total">{formatMoney(order.total)} ₽</span>
          {Number(order.prepayment) > 0 && Number(order.to_pay) > 0 && (
            <span className="text-muted">доплата {formatMoney(order.to_pay)} ₽</span>
          )}
        </div>
        {canManage && next && (
          <Button
            variant={next === 'issued' ? 'primary' : 'secondary'}
            onClick={(e) => {
              e.stopPropagation()
              onAdvance(order)
            }}
          >
            {next === 'issued' ? 'Выдать' : `→ ${ORDER_STATUS_LABELS[next]}`}
          </Button>
        )}
      </div>
    </div>
  )
}

function OrdersCalendarView({
  orders,
  clientName,
  onSelect,
}: {
  orders: Order[]
  clientName: (id: number) => string
  onSelect: (order: Order) => void
}) {
  const [cursor, setCursor] = useState(() => new Date())
  const year = cursor.getFullYear()
  const month = cursor.getMonth()

  const byDay = useMemo(() => {
    const map = new Map<string, Order[]>()
    for (const o of orders) {
      if (!o.due_date) continue
      const list = map.get(o.due_date) ?? []
      list.push(o)
      map.set(o.due_date, list)
    }
    return map
  }, [orders])

  const unscheduled = useMemo(() => orders.filter((o) => !o.due_date), [orders])

  const cells = useMemo(() => {
    const first = new Date(year, month, 1)
    const startOffset = (first.getDay() + 6) % 7
    const start = new Date(year, month, 1 - startOffset)
    return Array.from(
      { length: 42 },
      (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i),
    )
  }, [year, month])

  const todayISO = toISODate(new Date())

  return (
    <div className="view-calendar">
      <div className="view-calendar-header">
        <div className="view-calendar-nav">
          <IconButton
            variant="muted"
            onClick={() => setCursor(new Date(year, month - 1, 1))}
            aria-label="Предыдущий месяц"
          >
            <IconChevronLeft size={16} stroke={1.8} />
          </IconButton>
          <IconButton
            variant="muted"
            onClick={() => setCursor(new Date(year, month + 1, 1))}
            aria-label="Следующий месяц"
          >
            <IconChevronRight size={16} stroke={1.8} />
          </IconButton>
        </div>
        <span className="view-calendar-title">
          {MONTHS[month]} {year}
        </span>
        <Button variant="secondary" onClick={() => setCursor(new Date())}>
          Сегодня
        </Button>
      </div>
      <div className="view-calendar-weekdays">
        {WEEKDAYS.map((w) => (
          <span key={w}>{w}</span>
        ))}
      </div>
      <div className="view-calendar-grid">
        {cells.map((date, i) => {
          const iso = toISODate(date)
          const inMonth = date.getMonth() === month
          const dayOrders = byDay.get(iso) ?? []
          const visible = dayOrders.slice(0, 3)
          const overflow = dayOrders.length - visible.length
          return (
            <div key={i} className={`view-calendar-cell${inMonth ? '' : ' view-calendar-cell-outside'}`}>
              <span className={`view-calendar-date${iso === todayISO ? ' view-calendar-date-today' : ''}`}>
                {date.getDate()}
              </span>
              {visible.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  className="view-calendar-entry"
                  onClick={() => onSelect(o)}
                  title={`№${o.number ?? o.id} · ${clientName(o.client_id)}`}
                >
                  {clientName(o.client_id)}
                </button>
              ))}
              {overflow > 0 && <span className="view-calendar-entry view-calendar-entry-more">+{overflow}</span>}
            </div>
          )
        })}
      </div>
      {unscheduled.length > 0 && (
        <div className="view-calendar-unscheduled">
          <span className="view-calendar-unscheduled-title">Без даты готовности · {unscheduled.length}</span>
          <div className="orders-history-list">
            {unscheduled.map((o) => (
              <div key={o.id} className="card orders-history-card" onClick={() => onSelect(o)}>
                <div className="orders-history-card-main">
                  <div className="orders-history-card-title">
                    <strong>№{o.number ?? o.id}</strong>
                    <span>{clientName(o.client_id)}</span>
                    <span className={ORDER_STATUS_BADGE_CLASS[o.status]}>{ORDER_STATUS_LABELS[o.status]}</span>
                  </div>
                </div>
                <span className="orders-board-card-total">{formatMoney(o.total)} ₽</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function IssueOrderModal({
  order,
  onClose,
  onIssued,
}: {
  order: Order
  onClose: () => void
  onIssued: (result: IssueOrderResult) => void
}) {
  const [payment, setPayment] = useState<PaymentMethod>('cash')
  const [cashReceived, setCashReceived] = useState('')
  const [debtDueDate, setDebtDueDate] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toPayCents = Math.round(Number(order.to_pay) * 100)
  const cashReceivedCents = Math.round(Number(cashReceived || 0) * 100)
  const changeCents = cashReceivedCents - toPayCents
  const change = centsToMoney(Math.max(0, changeCents))

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (payment === 'credit' && !debtDueDate) {
      setError('Для выдачи в долг укажите срок «Долг до»')
      return
    }
    setError(null)
    setSaving(true)
    try {
      const result = await issueOrder(order.id, {
        payment_method: payment,
        cash_received: payment === 'cash' && cashReceived ? cashReceived : null,
        debt_due_date: payment === 'credit' ? debtDueDate : null,
      })
      onIssued(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось выдать заказ')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={`Выдать заказ №${order.number ?? order.id}`} onClose={onClose}>
      <form className="form" onSubmit={handleSubmit}>
        <div className="sale-detail-totals">
          <div className="sale-detail-totals-row">
            <span>Сумма заказа</span>
            <span>{formatMoney(order.total)} ₽</span>
          </div>
          {Number(order.prepayment) > 0 && (
            <div className="sale-detail-totals-row">
              <span>Предоплата</span>
              <span>−{formatMoney(order.prepayment)} ₽</span>
            </div>
          )}
          <div className="sale-detail-totals-row sale-detail-totals-row-sum">
            <span>К оплате сейчас</span>
            <span>{formatMoney(order.to_pay)} ₽</span>
          </div>
        </div>

        <label className="field">
          Способ оплаты
          <Select
            value={payment}
            onChange={(v) => setPayment(v as PaymentMethod)}
            options={Object.entries(PAYMENT_LABELS).map(([value, label]) => ({ value, label }))}
          />
        </label>

        {payment === 'cash' && (
          <label className="field">
            Получено
            <input
              type="text"
              inputMode="decimal"
              placeholder={formatMoney(order.to_pay)}
              value={cashReceived}
              onChange={(e) => {
                const normalized = normalizeDecimalInput(e.target.value)
                if (normalized !== null) setCashReceived(normalized)
              }}
            />
            {cashReceivedCents > 0 && (
              <span className={changeCents < 0 ? 'sale-change-short' : 'text-muted'}>
                {changeCents >= 0
                  ? `Сдача: ${formatMoney(change)} ₽`
                  : `Не хватает: ${formatMoney(centsToMoney(-changeCents))} ₽`}
              </span>
            )}
          </label>
        )}

        {payment === 'credit' && (
          <label className="field">
            Долг до
            <DateInput
              required
              value={debtDueDate}
              min={new Date().toISOString().slice(0, 10)}
              onChange={setDebtDueDate}
            />
          </label>
        )}

        {error && <p className="error">{error}</p>}
        <Button type="submit" disabled={saving}>
          {saving ? 'Оформление…' : 'Выдать заказ'}
        </Button>
      </form>
    </Modal>
  )
}

function CancelOrderForm({
  order,
  onClose,
  onConfirm,
}: {
  order: Order
  onClose: () => void
  onConfirm: (reason: string) => Promise<void>
}) {
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleConfirm() {
    setSaving(true)
    setError(null)
    try {
      await onConfirm(reason)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось отменить заказ')
      setSaving(false)
    }
  }

  return (
    <Modal title={`Отменить заказ №${order.number ?? order.id}?`} onClose={onClose}>
      <div className="stack">
        <p>Резерв товара по заказу будет снят со склада. Это действие нельзя отменить.</p>
        <label className="field">
          Причина (необязательно)
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="клиент передумал…" />
        </label>
        {error && <p className="error">{error}</p>}
        <div className="row" style={{ gap: 8 }}>
          <Button variant="danger" onClick={handleConfirm} disabled={saving}>
            {saving ? 'Отмена…' : 'Да, отменить заказ'}
          </Button>
          <Button variant="secondary" onClick={onClose}>
            Не отменять
          </Button>
        </div>
      </div>
    </Modal>
  )
}

function OrderDetail({
  initialOrder,
  products,
  units,
  clients,
  warehouses,
  stock,
  canManage,
  onClose,
  onChanged,
}: {
  initialOrder: Order
  products: Product[]
  units: Unit[]
  clients: Client[]
  warehouses: Warehouse[]
  stock: StockItem[]
  canManage: boolean
  onClose: () => void
  onChanged: () => void
}) {
  const [order, setOrder] = useState(initialOrder)
  const [showEdit, setShowEdit] = useState(false)
  const [showCancel, setShowCancel] = useState(false)
  const [showIssue, setShowIssue] = useState(false)
  const [history, setHistory] = useState<OrderHistoryEntry[] | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [linkedSale, setLinkedSale] = useState<Sale | null>(null)

  const productName = (id: number) => products.find((p) => p.id === id)?.name ?? `#${id}`
  const client = clients.find((c) => c.id === order.client_id)
  const warehouseName = warehouses.find((w) => w.id === order.warehouse_id)?.name ?? `#${order.warehouse_id}`
  const isTerminal = order.status === 'issued' || order.status === 'cancelled'

  useEffect(() => {
    if (order.sale_id == null) return
    getSale(order.sale_id).then(setLinkedSale).catch(() => {})
  }, [order.sale_id])

  async function toggleHistory() {
    if (historyOpen) {
      setHistoryOpen(false)
      return
    }
    setHistoryOpen(true)
    if (history !== null) return
    setLoadingHistory(true)
    try {
      setHistory(await getOrderHistory(order.id))
    } catch {
      setHistory([])
    } finally {
      setLoadingHistory(false)
    }
  }

  const headerActions = canManage && !isTerminal && (
    <>
      <IconButton
        variant="muted"
        size="lg"
        onClick={() => setShowEdit(true)}
        tooltip="Редактировать заказ"
        aria-label="Редактировать заказ"
      >
        <IconPencil size={22} stroke={1.8} />
      </IconButton>
      <IconButton
        variant="danger"
        size="lg"
        onClick={() => setShowCancel(true)}
        tooltip="Отменить заказ"
        aria-label="Отменить заказ"
      >
        <IconBan size={22} stroke={1.8} />
      </IconButton>
    </>
  )

  return (
    <Modal title={`Заказ №${order.number ?? order.id}`} onClose={onClose} size="wide" headerActions={headerActions}>
      <div className="stack">
        <div className="row between wrap" style={{ gap: 10 }}>
          <span className={ORDER_STATUS_BADGE_CLASS[order.status]}>{ORDER_STATUS_LABELS[order.status]}</span>
          {canManage && order.status === 'ready' && (
            <Button onClick={() => setShowIssue(true)}>Выдать и оформить продажу</Button>
          )}
        </div>

        <div className="sale-detail-meta">
          <div className="sale-detail-meta-item">
            <span className="text-muted">Источник</span>
            <span>{ORDER_SOURCE_LABELS[order.source]}</span>
          </div>
          <div className="sale-detail-meta-item">
            <span className="text-muted">Склад</span>
            <span>{warehouseName}</span>
          </div>
          {order.due_date && (
            <div className="sale-detail-meta-item">
              <span className="text-muted">Дата готовности</span>
              <span>{formatDueDate(order.due_date)}</span>
            </div>
          )}
          {order.created_at && (
            <div className="sale-detail-meta-item">
              <span className="text-muted">Создан</span>
              <span>{formatDateTime(order.created_at)}</span>
            </div>
          )}
          {linkedSale && (
            <div className="sale-detail-meta-item">
              <span className="text-muted">Оплата при выдаче</span>
              <span className={PAYMENT_BADGE_CLASS[linkedSale.payment_method]}>
                {PAYMENT_LABELS[linkedSale.payment_method]}
              </span>
            </div>
          )}
        </div>

        {client && (
          <div className="sale-detail-client-card">
            <Link to={`/clients?highlight=${client.id}`} className="sale-detail-client-link">
              <IconUsers size={16} stroke={1.8} />
              <span className="sale-detail-client-name">{client.name}</span>
            </Link>
            <Link to={`/clients?highlight=${client.id}`} className="sale-detail-client-arrow-link">
              <IconChevronRight size={16} stroke={1.8} className="sale-detail-client-arrow" />
            </Link>
          </div>
        )}

        <h3 className="sale-detail-section-title">
          Товары <span className="text-muted">· {order.lines.length} поз.</span>
        </h3>
        <div className="data-table">
          <div className="data-table-head" style={{ gridTemplateColumns: ORDER_LINES_COLUMNS }}>
            <span>Товар</span>
            <span>Кол-во</span>
            <span>Цена</span>
            <span>Сумма</span>
          </div>
          <div className="data-table-body">
            {order.lines.map((line, i) => (
              <div
                key={i}
                className="data-row sale-history-row-in"
                style={
                  {
                    gridTemplateColumns: ORDER_LINES_COLUMNS,
                    '--row-delay': `${Math.min(i, 12) * 25}ms`,
                  } as CSSProperties
                }
              >
                <span className="data-row-name">{productName(line.product_id)}</span>
                <span>{formatQuantity(line.quantity)}</span>
                <span>{formatMoney(line.price)} ₽</span>
                <span>{formatMoney(line.total)} ₽</span>
              </div>
            ))}
          </div>
        </div>

        <div className="sale-detail-totals">
          <div className="sale-detail-totals-row">
            <span>Итого</span>
            <span>{formatMoney(order.total)} ₽</span>
          </div>
          {Number(order.prepayment) > 0 && (
            <div className="sale-detail-totals-row">
              <span>Предоплата</span>
              <span>−{formatMoney(order.prepayment)} ₽</span>
            </div>
          )}
          <div className="sale-detail-totals-row sale-detail-totals-row-sum">
            <span>К доплате</span>
            <span>{formatMoney(order.to_pay)} ₽</span>
          </div>
        </div>

        {order.note && (
          <div className="stack" style={{ gap: 2 }}>
            <span className="field-label">Заметка</span>
            <span className="text-muted" style={{ whiteSpace: 'pre-wrap' }}>
              {order.note}
            </span>
          </div>
        )}

        <div className="sale-detail-history">
          <button
            type="button"
            className="disclosure-link"
            onClick={toggleHistory}
            disabled={loadingHistory}
            aria-expanded={historyOpen}
          >
            {loadingHistory ? 'Загрузка…' : 'История изменений'}
            <IconChevronDown size={14} stroke={1.8} />
          </button>
          {historyOpen &&
            (history === null ? null : history.length === 0 ? (
              <p className="text-muted">Изменений не было</p>
            ) : (
              <div className="sale-detail-history-list">
                {history.map((entry) => {
                  const HistoryIcon = ORDER_HISTORY_ACTION_ICONS[entry.action] ?? IconArrowRight
                  return (
                    <div key={entry.id} className="sale-detail-history-item">
                      <span className="sale-detail-history-icon">
                        <HistoryIcon size={15} stroke={1.8} />
                      </span>
                      <span className="sale-detail-history-label">
                        {ORDER_HISTORY_ACTION_LABELS[entry.action] ?? entry.action}
                      </span>
                      <span className="sale-detail-history-time">{formatDateTime(entry.created_at)}</span>
                    </div>
                  )
                })}
              </div>
            ))}
        </div>
      </div>

      {showEdit && (
        <Modal title="Редактировать заказ" onClose={() => setShowEdit(false)} size="full">
          <NewOrderForm
            products={products}
            units={units}
            clients={clients}
            warehouses={warehouses}
            stock={stock}
            editOrder={order}
            onDone={(updated) => {
              setOrder(updated)
              setShowEdit(false)
              onChanged()
            }}
          />
        </Modal>
      )}

      {showCancel && (
        <CancelOrderForm
          order={order}
          onClose={() => setShowCancel(false)}
          onConfirm={async (reason) => {
            const updated = await cancelOrder(order.id, reason)
            setOrder(updated)
            setShowCancel(false)
            onChanged()
          }}
        />
      )}

      {showIssue && (
        <IssueOrderModal
          order={order}
          onClose={() => setShowIssue(false)}
          onIssued={(result) => {
            setOrder(result.order)
            setShowIssue(false)
            onChanged()
          }}
        />
      )}
    </Modal>
  )
}

interface OrderFormLine {
  product: Product
  quantity: string
  price: string
}

function NewOrderForm({
  products,
  units,
  clients,
  warehouses,
  stock,
  editOrder,
  onDone,
}: {
  products: Product[]
  units: Unit[]
  clients: Client[]
  warehouses: Warehouse[]
  stock: StockItem[]
  editOrder?: Order
  onDone: (order: Order) => void
}) {
  const [clientId, setClientId] = useState<number | null>(editOrder?.client_id ?? clients[0]?.id ?? null)
  const [warehouseId, setWarehouseId] = useState<number | null>(editOrder?.warehouse_id ?? warehouses[0]?.id ?? null)
  const [source, setSource] = useState<OrderSource>(editOrder?.source ?? 'in_person')
  const [lines, setLines] = useState<OrderFormLine[]>(() =>
    (editOrder?.lines ?? [])
      .map((l) => {
        const product = products.find((p) => p.id === l.product_id)
        return product ? { product, quantity: l.quantity, price: l.price } : null
      })
      .filter((l): l is OrderFormLine => l !== null),
  )
  const [query, setQuery] = useState('')
  const [dueDate, setDueDate] = useState(editOrder?.due_date ?? '')
  const [prepayment, setPrepayment] = useState(editOrder?.prepayment ?? '0')
  const [note, setNote] = useState(editOrder?.note ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [showScanner, setShowScanner] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)

  const isFractional = (code: string) => units.find((u) => u.code === code)?.fractional ?? false
  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code

  const stockFor = (productId: number) =>
    warehouseId == null
      ? null
      : stock.find((s) => s.product_id === productId && s.warehouse_id === warehouseId)?.available ?? null

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return products
    return products.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.sku.toLowerCase().includes(q) ||
        (p.barcode ?? '').toLowerCase().includes(q),
    )
  }, [products, query])

  function addLine(product: Product) {
    setLines((prev) => {
      const existing = prev.find((l) => l.product.id === product.id)
      if (existing) {
        return prev.map((l) =>
          l.product.id === product.id ? { ...l, quantity: String(Number(l.quantity) + 1) } : l,
        )
      }
      return [...prev, { product, quantity: '1', price: String(Number(product.retail_price)) }]
    })
  }

  function updateLine(productId: number, field: 'quantity' | 'price', rawValue: string) {
    const normalized = normalizeDecimalInput(rawValue)
    if (normalized === null) return
    setLines((prev) =>
      prev.map((l) => {
        if (l.product.id !== productId) return l
        let value = normalized
        if (field === 'quantity' && !isFractional(l.product.unit_code) && value.includes('.')) {
          value = value.split('.')[0] || '0'
        }
        return { ...l, [field]: value }
      }),
    )
  }

  function stepLineQuantity(productId: number, delta: number) {
    setLines((prev) =>
      prev.map((l) => {
        if (l.product.id !== productId) return l
        const next = Math.max(0, Number(l.quantity || 0) + delta)
        const quantity = isFractional(l.product.unit_code)
          ? (Number.isInteger(next) ? next.toFixed(1) : String(next))
          : String(Math.round(next))
        return { ...l, quantity }
      }),
    )
  }

  function removeLine(productId: number) {
    setLines((prev) => prev.filter((l) => l.product.id !== productId))
  }

  async function handleScan(code: string) {
    setShowScanner(false)
    setScanError(null)
    try {
      const product = await getByBarcode(code)
      if (product) {
        addLine(product)
      } else {
        setScanError(`Товар со штрихкодом ${code} не найден`)
      }
    } catch {
      setScanError('Не удалось найти товар по штрихкоду')
    }
  }

  const total = lines.reduce((sum, l) => sum + Number(l.quantity || 0) * Number(l.price || 0), 0)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!clientId || !warehouseId || !dueDate || lines.length === 0) return
    setError(null)
    setSaving(true)
    try {
      const input: OrderFormInput = {
        client_id: clientId,
        warehouse_id: warehouseId,
        items: lines.map((l) => ({
          product_id: l.product.id,
          quantity: l.quantity,
          price: l.price,
        })),
        due_date: dueDate,
        prepayment,
        source,
        note,
      }
      const order = editOrder ? await updateOrder(editOrder.id, input) : await createOrder(input)
      onDone(order)
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : `Не удалось ${editOrder ? 'сохранить' : 'создать'} заказ`,
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <div className="row">
        <label className="field" style={{ flex: 1 }}>
          Клиент
          <Select
            value={clientId != null ? String(clientId) : ''}
            onChange={(v) => setClientId(Number(v))}
            options={clients.map((c) => ({ value: String(c.id), label: c.name }))}
          />
        </label>
        {warehouses.length > 1 && (
          <label className="field" style={{ flex: 1 }}>
            Склад
            <Select
              value={warehouseId != null ? String(warehouseId) : ''}
              onChange={(v) => setWarehouseId(Number(v))}
              options={warehouses.map((w) => ({ value: String(w.id), label: w.name }))}
            />
          </label>
        )}
        <label className="field" style={{ flex: 1 }}>
          Источник
          <Select
            value={source}
            onChange={(v) => setSource(v as OrderSource)}
            options={Object.entries(ORDER_SOURCE_LABELS).map(([value, label]) => ({ value, label }))}
          />
        </label>
      </div>

      <div className="stack" style={{ gap: 10 }}>
        <div className="sale-search-row">
          <input
            className="sale-search-input"
            placeholder="Поиск по названию, артикулу, штрихкоду…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {isBarcodeScannerSupported() && (
            <Button type="button" variant="secondary" onClick={() => setShowScanner(true)}>
              <IconBarcode size={16} stroke={1.8} />
            </Button>
          )}
        </div>
        {scanError && <p className="error">{scanError}</p>}
        <div className="sale-results-header">
          <span>Товары</span>
          <span className="text-muted">{filtered.length} найдено</span>
        </div>
        {filtered.length === 0 ? (
          <p className="text-muted">Ничего не найдено</p>
        ) : (
          <div className="product-grid" style={{ maxHeight: 480, minHeight: 220, overflowY: 'auto' }}>
            {filtered.map((p) => {
              const inLineQty = lines.find((l) => l.product.id === p.id)?.quantity
              const available = stockFor(p.id)
              return (
                <div
                  key={p.id}
                  role="button"
                  tabIndex={0}
                  className={`product-tile${inLineQty ? ' product-tile-in-cart' : ''}`}
                  onClick={() => addLine(p)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      addLine(p)
                    }
                  }}
                >
                  <ProductPhoto src={p.photo} />
                  <div className="product-tile-body">
                    <span className="product-tile-name">{p.name}</span>
                    <span className="product-tile-price-label">Цена за {unitName(p.unit_code)}:</span>
                    <span className="product-tile-price">{formatMoney(p.retail_price)} ₽</span>
                    {available !== null && (
                      <span
                        className={`product-tile-stock${
                          isOutOfStock(available) ? ' product-tile-stock-out' : ' product-tile-stock-in'
                        }`}
                      >
                        <span className="product-tile-stock-label">Доступно:</span>
                        <span className="product-tile-stock-value-wrap">
                          <span className="product-tile-stock-value">
                            {formatQuantity(available)} {unitName(p.unit_code)}
                          </span>
                          {isLowStock(available, p.min_stock) && <StockWarningIcon />}
                        </span>
                      </span>
                    )}
                  </div>
                  <span
                    className={`product-tile-cart-badge${inLineQty ? '' : ' product-tile-cart-badge-hidden'}`}
                  >
                    {inLineQty ? (
                      <>
                        {formatQuantity(inLineQty)}
                        <IconButton
                          className="product-tile-remove"
                          onClick={(e) => {
                            e.stopPropagation()
                            removeLine(p.id)
                          }}
                          aria-label="Убрать из списка"
                        >
                          <IconTrash size={10} stroke={1.8} />
                        </IconButton>
                      </>
                    ) : (
                      ' '
                    )}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {showScanner && (
        <Modal title="Сканировать штрихкод" onClose={() => setShowScanner(false)}>
          <Suspense fallback={<p className="text-muted">Загрузка сканера…</p>}>
            <BarcodeScanner onDetected={handleScan} onClose={() => setShowScanner(false)} />
          </Suspense>
        </Modal>
      )}

      {lines.length > 0 && (
        <div className="stack card card-full">
          <div className="section-title">
            <h3>Позиции заказа</h3>
            <span className="text-muted">{lines.length} поз.</span>
          </div>
          <div className="table-wrap cart-table-wrap cart-table-wrap-compact">
            <div className="cart-table-head" style={{ gridTemplateColumns: '34% 27% 27% 12%' }}>
              <span>Товар</span>
              <span>Кол-во</span>
              <span>Цена</span>
              <span />
            </div>
            <div>
              {lines.map((line) => {
                const available = stockFor(line.product.id)
                const overStock = available !== null && Number(line.quantity || 0) > Number(available)
                return (
                  <div
                    key={line.product.id}
                    className="cart-table-row"
                    style={{ gridTemplateColumns: '34% 27% 27% 12%' }}
                  >
                    <div className="cart-table-name">
                      <div>{line.product.name}</div>
                      {available !== null && (
                        <div className="cart-table-stock">
                          Доступно: {formatQuantity(available)} {unitName(line.product.unit_code)}
                        </div>
                      )}
                    </div>
                    <div className="cart-table-qty-cell">
                      <div className="cart-qty-stepper">
                        <input
                          type="text"
                          inputMode="decimal"
                          className={overStock ? 'cart-input-warning' : undefined}
                          value={line.quantity}
                          onChange={(e) => updateLine(line.product.id, 'quantity', e.target.value)}
                        />
                        <div className="cart-qty-step-column">
                          <IconButton
                            variant="muted"
                            className="cart-qty-step"
                            onClick={() => stepLineQuantity(line.product.id, 1)}
                            aria-label="Увеличить количество"
                          >
                            <IconChevronRight size={10} stroke={1.8} className="cart-qty-step-icon-up" />
                          </IconButton>
                          <IconButton
                            variant="muted"
                            className="cart-qty-step"
                            onClick={() => stepLineQuantity(line.product.id, -1)}
                            aria-label="Уменьшить количество"
                          >
                            <IconChevronRight size={10} stroke={1.8} className="cart-qty-step-icon-down" />
                          </IconButton>
                        </div>
                      </div>
                      {overStock && available !== null && (
                        <div className="cart-table-warning">больше доступного ({formatQuantity(available)})</div>
                      )}
                    </div>
                    <div className="cart-table-price-cell">
                      <input
                        type="text"
                        inputMode="decimal"
                        value={line.price}
                        onChange={(e) => updateLine(line.product.id, 'price', e.target.value)}
                      />
                      <span className="cart-table-price-suffix">₽</span>
                    </div>
                    <IconButton
                      variant="danger"
                      onClick={() => removeLine(line.product.id)}
                      aria-label="Убрать позицию"
                    >
                      <IconTrash size={16} stroke={1.8} />
                    </IconButton>
                  </div>
                )
              })}
            </div>
          </div>
          <div className="row between">
            <span className="text-muted">Итого</span>
            <strong>{formatMoney(total)} ₽</strong>
          </div>
        </div>
      )}

      <div className="row">
        <label className="field" style={{ flex: 1 }}>
          Дата готовности
          <DateInput required value={dueDate} onChange={setDueDate} />
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
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="из директа, размер, пожелания…" />
      </label>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving || !clientId || !warehouseId || !dueDate || lines.length === 0}>
        {saving ? 'Сохранение…' : editOrder ? 'Сохранить изменения' : 'Создать заказ'}
      </Button>
    </form>
  )
}
