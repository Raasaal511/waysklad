import { useEffect, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import {
  cancelOrder,
  getOrderHistory,
  type Order,
} from '../../entities/order/api'
import {
  ORDER_STATUS_LABELS,
  ORDER_STATUS_BADGE_CLASS,
} from '../../entities/order/orderStatus'
import type { Warehouse, StockItem } from '../../entities/inventory/api'
import type { Client } from '../../entities/counterparty/api'
import type { Product, Unit } from '../../entities/product/api'
import { getSale, type Sale } from '../../entities/sale/api'
import {
  IconPencil,
  IconBan,
  IconCheck,
  IconArrowRight,
  IconReceipt2,
  IconUsers,
  IconChevronRight,
  IconCalendar,
  IconBuildingWarehouse,
  IconCoin,
  IconCash,
  IconClock,
  type Icon as TablerIcon,
} from '@tabler/icons-react'
import { Modal } from '../../shared/ui/Modal'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { HistoryDisclosure } from '../../shared/ui/HistoryDisclosure'
import { formatMoney, formatQuantity } from '../../shared/lib/format'
import { PAYMENT_LABELS, PAYMENT_BADGE_CLASS } from '../sales/saleDraft'
import { NewOrderForm } from './NewOrderForm'
import { IssueOrderModal } from './IssueOrderModal'
import { CancelOrderForm } from './CancelOrderForm'
import {
  ORDER_SOURCE_LABELS,
  ORDER_HISTORY_ACTION_LABELS,
  formatOrderHistoryDetail,
  formatDateTime,
  formatDueDate,
  isOverdue,
} from './orderLabels'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './OrdersPage.module.css'
import detailStyles from './OrderDetailPage.module.css'

const ORDER_LINES_COLUMNS = '2fr 1fr 1fr 1fr'

const ORDER_HISTORY_ACTION_ICONS: Record<string, TablerIcon> = {
  'order.create': IconCheck,
  'order.update': IconPencil,
  'order.status': IconArrowRight,
  'order.cancel': IconBan,
  'order.issue': IconReceipt2,
}

export function OrderDetailView({
  order: initialOrder,
  products,
  units,
  clients,
  warehouses,
  stock,
  canManage,
  onDone,
  onUpdated,
}: {
  order: Order
  products: Product[]
  units: Unit[]
  clients: Client[]
  warehouses: Warehouse[]
  stock: StockItem[]
  canManage: boolean
  onDone: () => void
  onUpdated: () => void
}) {
  const [order, setOrder] = useState(initialOrder)
  const [showEdit, setShowEdit] = useState(false)
  const [showCancel, setShowCancel] = useState(false)
  const [showIssue, setShowIssue] = useState(false)
  const [linkedSale, setLinkedSale] = useState<Sale | null>(null)

  useEffect(() => {
    setOrder(initialOrder)
  }, [initialOrder])

  useEffect(() => {
    if (order.sale_id == null) {
      setLinkedSale(null)
      return
    }
    getSale(order.sale_id).then(setLinkedSale).catch(() => {})
  }, [order.sale_id])

  const productName = (id: number) => products.find((p) => p.id === id)?.name ?? `#${id}`
  const client = clients.find((c) => c.id === order.client_id)
  const warehouseName = warehouses.find((w) => w.id === order.warehouse_id)?.name ?? `#${order.warehouse_id}`
  const isTerminal = order.status === 'issued' || order.status === 'cancelled'

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
    <div className={layoutStyles.stack}>
      <section className={`${detailStyles.hero} ${detailStyles.reveal}`} style={{ '--reveal-delay': '0ms' } as CSSProperties}>
        <div className={detailStyles.heroBody}>
          <div className={detailStyles.heroTop}>
            <div className={detailStyles.heroHeading}>
              <h2 className={detailStyles.heroTitle}>Заказ №{order.number ?? order.id}</h2>
              <div className={detailStyles.heroTags}>
                <span className={ORDER_STATUS_BADGE_CLASS[order.status]}>
                  {ORDER_STATUS_LABELS[order.status]}
                </span>
                <span className="badge">{ORDER_SOURCE_LABELS[order.source]}</span>
                {order.sale_id != null && (
                  <Link to={`/sales/${order.sale_id}`} className="badge accent">
                    Продажа №{order.sale_id}
                  </Link>
                )}
              </div>
            </div>
            <div className={layoutStyles.row} style={{ gap: 8, flexWrap: 'wrap' }}>
              {canManage && order.status === 'ready' && (
                <Button onClick={() => setShowIssue(true)}>Выдать и оформить продажу</Button>
              )}
              {headerActions}
            </div>
          </div>
          <div className={detailStyles.heroPrice}>{formatMoney(order.total)} ₽</div>
          <div className={detailStyles.heroMeta}>
            {order.due_date && (
              <span className={isOverdue(order.due_date) ? styles.ordersBoardCardDueOverdue : undefined}>
                <IconClock size={15} stroke={1.8} />
                до {formatDueDate(order.due_date)}
              </span>
            )}
            <span>
              <IconBuildingWarehouse size={15} stroke={1.8} />
              {warehouseName}
            </span>
            {order.created_at && (
              <span>
                <IconCalendar size={15} stroke={1.8} />
                {formatDateTime(order.created_at)}
              </span>
            )}
          </div>
        </div>
      </section>

      <section
        className={`${detailStyles.metrics} ${detailStyles.reveal}`}
        style={{ '--reveal-delay': '60ms' } as CSSProperties}
      >
        <div className={detailStyles.metric}>
          <span className={detailStyles.metricIcon}>
            <IconCoin size={18} stroke={1.8} />
          </span>
          <div className={detailStyles.metricBody}>
            <strong>{formatMoney(order.total)} ₽</strong>
            <span>Итого</span>
          </div>
        </div>
        {Number(order.prepayment) > 0 && (
          <div className={detailStyles.metric}>
            <span className={detailStyles.metricIcon}>
              <IconCash size={18} stroke={1.8} />
            </span>
            <div className={detailStyles.metricBody}>
              <strong>{formatMoney(order.prepayment)} ₽</strong>
              <span>Предоплата</span>
            </div>
          </div>
        )}
        <div className={detailStyles.metric}>
          <span className={detailStyles.metricIcon}>
            <IconCash size={18} stroke={1.8} />
          </span>
          <div className={detailStyles.metricBody}>
            <strong>{formatMoney(order.to_pay)} ₽</strong>
            <span>К доплате</span>
          </div>
        </div>
        <div className={detailStyles.metric}>
          <span className={detailStyles.metricIcon}>
            <IconBuildingWarehouse size={18} stroke={1.8} />
          </span>
          <div className={detailStyles.metricBody}>
            <strong>{warehouseName}</strong>
            <span>Склад</span>
          </div>
        </div>
        {linkedSale && (
          <div className={detailStyles.metric}>
            <span className={detailStyles.metricIcon}>
              <IconReceipt2 size={18} stroke={1.8} />
            </span>
            <div className={detailStyles.metricBody}>
              <strong>
                <span className={PAYMENT_BADGE_CLASS[linkedSale.payment_method]}>
                  {PAYMENT_LABELS[linkedSale.payment_method]}
                </span>
              </strong>
              <span>Оплата при выдаче</span>
            </div>
          </div>
        )}
      </section>

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

      <section className={`${detailStyles.section} ${detailStyles.reveal}`} style={{ '--reveal-delay': '110ms' } as CSSProperties}>
        <h3 className={detailStyles.sectionTitle}>
          Товары <span className={layoutStyles.textMuted}>· {order.lines.length} поз.</span>
        </h3>
        <div className={layoutStyles.dataTable}>
          <div className={layoutStyles.dataTableHead} style={{ gridTemplateColumns: ORDER_LINES_COLUMNS }}>
            <span>Товар</span>
            <span>Кол-во</span>
            <span>Цена</span>
            <span>Сумма</span>
          </div>
          <div className={layoutStyles.dataTableBody}>
            {order.lines.map((line, i) => (
              <div
                key={i}
                className={[layoutStyles.dataRow, 'sale-history-row-in'].join(' ')}
                style={
                  {
                    gridTemplateColumns: ORDER_LINES_COLUMNS,
                    '--row-delay': `${Math.min(i, 12) * 25}ms`,
                  } as CSSProperties
                }
              >
                <span className={layoutStyles.dataRowName}>{productName(line.product_id)}</span>
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
      </section>

      {order.note && (
        <div className={layoutStyles.stack} style={{ gap: 2 }}>
          <span className={layoutStyles.fieldLabel}>Заметка</span>
          <span className={layoutStyles.textMuted} style={{ whiteSpace: 'pre-wrap' }}>
            {order.note}
          </span>
        </div>
      )}

      <HistoryDisclosure
        load={() => getOrderHistory(order.id)}
        actionLabels={ORDER_HISTORY_ACTION_LABELS}
        formatDetail={formatOrderHistoryDetail}
        actionIcons={ORDER_HISTORY_ACTION_ICONS}
        defaultIcon={IconArrowRight}
      />

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
              onUpdated()
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
            onUpdated()
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
            onUpdated()
          }}
        />
      )}
    </div>
  )
}
