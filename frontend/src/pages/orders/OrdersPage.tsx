import { useEffect, useMemo, useState, type CSSProperties, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  listActiveOrders,
  listCompletedOrders,
  changeOrderStatus,
  type Order,
  type OrderStatus,
} from '../../entities/order/api'
import {
  ORDER_STATUS_LABELS,
  ORDER_STATUS_BADGE_CLASS,
  NEXT_STATUS,
  BOARD_STATUSES,
  STATUS_ACCENT,
} from '../../entities/order/orderStatus'
import { searchClients, type Client } from '../../entities/counterparty/api'
import { useCatalog } from '../../app/CatalogContext'
import { ApiError } from '../../shared/api/client'
import {
  IconPlus,
  IconX,
  IconMessage2,
  IconReceipt2,
  IconArrowRight,
  IconClock,
  IconChevronRight,
  IconChevronLeft,
  IconBuildingStore,
  IconLayoutKanban,
  IconTable,
  IconList,
  IconCalendar,
  type Icon as TablerIcon,
} from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { formatMoney } from '../../shared/lib/format'
import { useAuth } from '../../app/AuthContext'
import { IssueOrderModal } from './IssueOrderModal'
import {
  ORDER_SOURCE_LABELS,
  ORDER_SOURCE_ICONS,
  formatDateTime,
  formatDueDate,
  isOverdue,
} from './orderLabels'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './OrdersPage.module.css'
import kanban from '../../shared/ui/KanbanBoard.module.css'
import { Avatar } from '../../shared/ui/Avatar'

const ONBOARDING_DISMISSED_KEY = 'orders_onboarding_dismissed'

type Tab = 'active' | 'completed'
type ViewMode = 'board' | 'table' | 'list' | 'calendar'

const VIEW_MODE_KEY = 'orders_view_mode'
const TAB_KEY = 'orders_tab'

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

export function OrdersPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = user?.role === 'owner' || user?.role === 'manager' || user?.role === 'seller'

  const { ensureProducts, ensureUnits, ensureWarehouses, ensureStock } = useCatalog()
  const [activeOrders, setActiveOrders] = useState<Order[]>([])
  const [completedOrders, setCompletedOrders] = useState<Order[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>(
    () => (localStorage.getItem(TAB_KEY) === 'completed' ? 'completed' : 'active'),
  )
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    const saved = localStorage.getItem(VIEW_MODE_KEY)
    return isViewMode(saved) ? saved : 'board'
  })
  const [showOnboarding, setShowOnboarding] = useState(
    () => localStorage.getItem(ONBOARDING_DISMISSED_KEY) !== '1',
  )
  const [draggedId, setDraggedId] = useState<number | null>(null)
  const [dragOverStatus, setDragOverStatus] = useState<OrderStatus | null>(null)
  const [issuingOrder, setIssuingOrder] = useState<Order | null>(null)

  useEffect(() => {
    localStorage.setItem(VIEW_MODE_KEY, viewMode)
  }, [viewMode])

  useEffect(() => {
    localStorage.setItem(TAB_KEY, tab)
  }, [tab])

  function dismissOnboarding() {
    setShowOnboarding(false)
    localStorage.setItem(ONBOARDING_DISMISSED_KEY, '1')
  }

  async function load(silent = false) {
    if (!silent) setLoading(true)
    try {
      const [active, completed, , , c] = await Promise.all([
        listActiveOrders(),
        listCompletedOrders(),
        ensureProducts(),
        ensureUnits(),
        searchClients(),
        ensureWarehouses(),
        ensureStock(),
      ])
      setActiveOrders(active)
      setCompletedOrders(completed)
      setClients(c)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить заказы')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const clientName = (id: number) => clients.find((c) => c.id === id)?.name ?? `#${id}`
  const openOrder = (order: Order) => navigate(`/orders/${order.id}`)

  async function moveTo(order: Order, newStatus: OrderStatus) {
    if (order.status === newStatus) return
    try {
      const updated = await changeOrderStatus(order.id, newStatus)
      const wasTerminal = order.status === 'issued' || order.status === 'cancelled'
      const isTerminalNow = newStatus === 'issued' || newStatus === 'cancelled'
      if (wasTerminal === isTerminalNow) {
        const updater = (prev: Order[]) => prev.map((o) => (o.id === order.id ? updated : o))
        if (isTerminalNow) setCompletedOrders(updater)
        else setActiveOrders(updater)
      } else {
        if (isTerminalNow) {
          setActiveOrders((prev) => prev.filter((o) => o.id !== order.id))
          setCompletedOrders((prev) => [updated, ...prev])
        } else {
          setCompletedOrders((prev) => prev.filter((o) => o.id !== order.id))
          setActiveOrders((prev) => [updated, ...prev])
        }
      }
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
    <div className={layoutStyles.stack}>
      <div className={layoutStyles.sectionTitle}>
        <h2>Заказы</h2>
        <div className={layoutStyles.row} style={{ gap: 8 }}>
          <Link to="/storefront?tab=requests">
            <Button variant="secondary">
              <IconBuildingStore size={16} stroke={1.8} /> Заявки с витрины
            </Button>
          </Link>
          {canManage && (
            <Button onClick={() => navigate('/orders/new')}>
              <IconPlus size={16} stroke={1.8} /> Заказ
            </Button>
          )}
        </div>
      </div>

      {showOnboarding && (
        <div className={[layoutStyles.card, layoutStyles.cardFull, styles.ordersIntro].join(' ')}>
          <IconButton
            variant="muted"
            className={styles.ordersIntroClose}
            tooltip="Понятно, больше не показывать"
            aria-label="Понятно, больше не показывать"
            onClick={dismissOnboarding}
          >
            <IconX size={16} stroke={1.8} />
          </IconButton>
          <div className={styles.ordersIntroFlow}>
            <div className={styles.ordersIntroStep}>
              <span className={styles.ordersIntroIcon}>
                <IconMessage2 size={20} stroke={1.8} />
              </span>
              <div className={layoutStyles.stack} style={{ gap: 2 }}>
                <strong>Заказ</strong>
                <span className={layoutStyles.textMuted}>Клиент попросил заранее — остаток резервируется на складе</span>
              </div>
            </div>
            <IconArrowRight size={18} stroke={1.8} className={styles.ordersIntroArrow} />
            <div className={styles.ordersIntroStep}>
              <span className={[styles.ordersIntroIcon, styles.ordersIntroIconAccent].join(' ')}>
                <IconReceipt2 size={20} stroke={1.8} />
              </span>
              <div className={layoutStyles.stack} style={{ gap: 2 }}>
                <strong>Выдача</strong>
                <span className={layoutStyles.textMuted}>Клиент забрал и доплатил — товар списан, продажа оформлена сама</span>
              </div>
            </div>
          </div>
        </div>
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

      <div className={[layoutStyles.row, layoutStyles.between, layoutStyles.wrap].join(' ')} style={{ gap: 10 }}>
        <div className="sale-period-tabs">
          <Button variant="secondary" active={tab === 'active'} onClick={() => setTab('active')}>
            Активные
            {activeOrders.length > 0 && <span className={layoutStyles.countBadge}>{activeOrders.length}</span>}
          </Button>
          <Button variant="secondary" active={tab === 'completed'} onClick={() => setTab('completed')}>
            Завершённые
            {completedOrders.length > 0 && <span className={layoutStyles.countBadge}>{completedOrders.length}</span>}
          </Button>
        </div>
        {tab === 'active' && (
          <div className={styles.viewSwitcher} role="tablist" aria-label="Вид отображения">
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

      {error && <p className={layoutStyles.error}>{error}</p>}
      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : tab === 'active' && viewMode === 'table' ? (
        <OrdersTableView orders={activeOrders} clientName={clientName} onSelect={openOrder} />
      ) : tab === 'active' && viewMode === 'list' ? (
        activeOrders.length === 0 ? (
          <p className={layoutStyles.textMuted}>Активных заказов пока нет</p>
        ) : (
          <div className={styles.ordersHistoryList}>
            {activeOrders.map((o) => (
              <OrderListRow
                key={o.id}
                order={o}
                clientName={clientName}
                canManage={canManage}
                onSelect={openOrder}
                onAdvance={handleAdvance}
              />
            ))}
          </div>
        )
      ) : tab === 'active' && viewMode === 'calendar' ? (
        <OrdersCalendarView orders={activeOrders} clientName={clientName} onSelect={openOrder} />
      ) : tab === 'active' ? (
        <div className={kanban.board} style={{ '--board-cols': BOARD_STATUSES.length } as CSSProperties}>
          {BOARD_STATUSES.map((status) => {
            const columnOrders = activeOrders.filter((o) => o.status === status)
            return (
              <div
                key={status}
                className={[kanban.column, dragOverStatus === status ? kanban.columnOver : null]
                  .filter(Boolean)
                  .join(' ')}
                style={{ '--col-accent': STATUS_ACCENT[status] } as CSSProperties}
                onDragOver={(e) => handleColumnDragOver(e, status)}
                onDragLeave={() => setDragOverStatus((s) => (s === status ? null : s))}
                onDrop={(e) => handleColumnDrop(e, status)}
              >
                <div className={kanban.columnHead}>
                  <span className={kanban.dot} />
                  <span>{ORDER_STATUS_LABELS[status]}</span>
                  <span className={kanban.columnCount}>{columnOrders.length}</span>
                  {status === 'new' && canManage && columnOrders.length > 0 && (
                    <IconButton
                      variant="accent"
                      className={styles.ordersBoardColumnAdd}
                      tooltip="Новый заказ"
                      aria-label="Новый заказ"
                      onClick={() => navigate('/orders/new')}
                    >
                      <IconPlus size={14} stroke={2} />
                    </IconButton>
                  )}
                </div>
                <div className={kanban.columnBody}>
                  {columnOrders.length === 0 ? (
                    status === 'new' && canManage ? (
                      <button
                        type="button"
                        className={[kanban.empty, kanban.emptyAction].join(' ')}
                        onClick={() => navigate('/orders/new')}
                      >
                        <IconPlus size={16} stroke={1.8} /> Создать заказ
                      </button>
                    ) : (
                      <div className={kanban.empty}>Пусто</div>
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
                          className={[kanban.card, draggedId === o.id ? kanban.cardDragging : null]
                            .filter(Boolean)
                            .join(' ')}
                          draggable={canManage}
                          onDragStart={() => handleDragStart(o)}
                          onDragEnd={handleDragEnd}
                          onClick={() => openOrder(o)}
                        >
                          <span className={kanban.cardAccent} />
                          <div className={kanban.cardHead}>
                            <span className={kanban.cardNumber}>
                              №{o.number ?? o.id}{' '}
                              <SourceIcon
                                size={13}
                                stroke={1.8}
                                className={layoutStyles.textMuted}
                                title={ORDER_SOURCE_LABELS[o.source]}
                              />
                            </span>
                            <span className={styles.ordersBoardCardTotal}>{formatMoney(o.total)} ₽</span>
                          </div>
                          <strong className={kanban.cardTitle}>{name}</strong>
                          <div className={kanban.cardFooter}>
                            {o.due_date ? (
                              <span
                                className={[
                                  kanban.cardDue,
                                  overdue ? styles.ordersBoardCardDueOverdue : null,
                                ]
                                  .filter(Boolean)
                                  .join(' ')}
                              >
                                <IconClock size={13} stroke={1.8} /> {formatDueDate(o.due_date)}
                              </span>
                            ) : partiallyPrepaid ? (
                              <span className="badge warning">
                                предоплата {formatMoney(o.prepayment)} ₽
                              </span>
                            ) : (
                              <span />
                            )}
                            <Avatar name={name} title={name} />
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
        <p className={layoutStyles.textMuted}>Завершённых заказов пока нет</p>
      ) : (
        <div className={styles.ordersHistoryList}>
          {orders.map((o) => (
            <div
              key={o.id}
              className={[layoutStyles.card, styles.ordersHistoryCard].join(' ')}
              onClick={() => openOrder(o)}
            >
              <div className={styles.ordersHistoryCardMain}>
                <div className={styles.ordersHistoryCardTitle}>
                  <strong>№{o.number ?? o.id}</strong>
                  <span>{clientName(o.client_id)}</span>
                  <span className={ORDER_STATUS_BADGE_CLASS[o.status]}>{ORDER_STATUS_LABELS[o.status]}</span>
                </div>
                {o.created_at && (
                  <span className={layoutStyles.textMuted}>
                    {o.status === 'cancelled' ? 'Создан' : 'Выдан'} {formatDateTime(o.created_at)}
                  </span>
                )}
              </div>
              <div className={styles.ordersHistoryCardMoney}>
                <span className={styles.ordersBoardCardTotal}>{formatMoney(o.total)} ₽</span>
                {o.status === 'issued' && Number(o.to_pay) > 0 && (
                  <span className={layoutStyles.textMuted}>доплата {formatMoney(o.to_pay)} ₽</span>
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
  if (orders.length === 0) return <p className={layoutStyles.textMuted}>Активных заказов пока нет</p>
  return (
    <div className={layoutStyles.dataTable}>
      <div className={layoutStyles.dataTableHead} style={{ gridTemplateColumns: ORDER_TABLE_COLUMNS }}>
        <span>№</span>
        <span>Клиент</span>
        <span>Источник</span>
        <span>Статус</span>
        <span>Сумма</span>
        <span>Срок</span>
        <span />
      </div>
      <div className={layoutStyles.dataTableBody}>
        {orders.map((o, i) => {
          const SourceIcon = ORDER_SOURCE_ICONS[o.source]
          const overdue = o.due_date != null && isOverdue(o.due_date)
          return (
            <button
              key={o.id}
              type="button"
              className={[layoutStyles.dataRow, layoutStyles.dataRowLink, 'sale-history-row-in'].join(' ')}
              style={
                {
                  gridTemplateColumns: ORDER_TABLE_COLUMNS,
                  '--row-delay': `${Math.min(i, 12) * 25}ms`,
                } as CSSProperties
              }
              onClick={() => onSelect(o)}
            >
              <span className={layoutStyles.dataRowName}>№{o.number ?? o.id}</span>
              <span>{clientName(o.client_id)}</span>
              <span className={[layoutStyles.row, layoutStyles.textMuted].join(' ')} style={{ gap: 4 }}>
                <SourceIcon size={14} stroke={1.8} /> {ORDER_SOURCE_LABELS[o.source]}
              </span>
              <span className={ORDER_STATUS_BADGE_CLASS[o.status]}>{ORDER_STATUS_LABELS[o.status]}</span>
              <span>{formatMoney(o.total)} ₽</span>
              <span className={overdue ? styles.ordersBoardCardDueOverdue : layoutStyles.textMuted}>
                {o.due_date ? formatDueDate(o.due_date) : '—'}
              </span>
              <IconChevronRight size={16} stroke={1.8} className={layoutStyles.dataRowChevron} />
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
    <div className={[layoutStyles.card, styles.ordersHistoryCard].join(' ')} onClick={() => onSelect(order)}>
      <div className={styles.ordersHistoryCardMain}>
        <div className={styles.ordersHistoryCardTitle}>
          <strong>№{order.number ?? order.id}</strong>
          <span>{clientName(order.client_id)}</span>
          <span className={ORDER_STATUS_BADGE_CLASS[order.status]}>{ORDER_STATUS_LABELS[order.status]}</span>
        </div>
        {order.due_date && (
          <span className={overdue ? styles.ordersBoardCardDueOverdue : layoutStyles.textMuted}>
            <IconClock size={13} stroke={1.8} /> до {formatDueDate(order.due_date)}
          </span>
        )}
      </div>
      <div className={layoutStyles.row} style={{ gap: 10 }}>
        <div className={styles.ordersHistoryCardMoney}>
          <span className={styles.ordersBoardCardTotal}>{formatMoney(order.total)} ₽</span>
          {Number(order.prepayment) > 0 && Number(order.to_pay) > 0 && (
            <span className={layoutStyles.textMuted}>доплата {formatMoney(order.to_pay)} ₽</span>
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
    <div className={styles.viewCalendar}>
      <div className={styles.viewCalendarHeader}>
        <div className={styles.viewCalendarNav}>
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
        <span className={styles.viewCalendarTitle}>
          {MONTHS[month]} {year}
        </span>
        <Button variant="secondary" onClick={() => setCursor(new Date())}>
          Сегодня
        </Button>
      </div>
      <div className={styles.viewCalendarWeekdays}>
        {WEEKDAYS.map((w) => (
          <span key={w}>{w}</span>
        ))}
      </div>
      <div className={styles.viewCalendarGrid}>
        {cells.map((date, i) => {
          const iso = toISODate(date)
          const inMonth = date.getMonth() === month
          const dayOrders = byDay.get(iso) ?? []
          const visible = dayOrders.slice(0, 3)
          const overflow = dayOrders.length - visible.length
          return (
            <div
              key={i}
              className={[styles.viewCalendarCell, inMonth ? null : styles.viewCalendarCellOutside]
                .filter(Boolean)
                .join(' ')}
            >
              <span
                className={[styles.viewCalendarDate, iso === todayISO ? styles.viewCalendarDateToday : null]
                  .filter(Boolean)
                  .join(' ')}
              >
                {date.getDate()}
              </span>
              {visible.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  className={styles.viewCalendarEntry}
                  onClick={() => onSelect(o)}
                  title={`№${o.number ?? o.id} · ${clientName(o.client_id)}`}
                >
                  {clientName(o.client_id)}
                </button>
              ))}
              {overflow > 0 && (
                <span className={[styles.viewCalendarEntry, styles.viewCalendarEntryMore].join(' ')}>
                  +{overflow}
                </span>
              )}
            </div>
          )
        })}
      </div>
      {unscheduled.length > 0 && (
        <div className={styles.viewCalendarUnscheduled}>
          <span className={styles.viewCalendarUnscheduledTitle}>Без даты готовности · {unscheduled.length}</span>
          <div className={styles.ordersHistoryList}>
            {unscheduled.map((o) => (
              <div
                key={o.id}
                className={[layoutStyles.card, styles.ordersHistoryCard].join(' ')}
                onClick={() => onSelect(o)}
              >
                <div className={styles.ordersHistoryCardMain}>
                  <div className={styles.ordersHistoryCardTitle}>
                    <strong>№{o.number ?? o.id}</strong>
                    <span>{clientName(o.client_id)}</span>
                    <span className={ORDER_STATUS_BADGE_CLASS[o.status]}>{ORDER_STATUS_LABELS[o.status]}</span>
                  </div>
                </div>
                <span className={styles.ordersBoardCardTotal}>{formatMoney(o.total)} ₽</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
