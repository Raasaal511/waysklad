import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
} from 'react'
import { Link } from 'react-router-dom'
import { type Warehouse } from '../../entities/inventory/api'
import { type Client } from '../../entities/counterparty/api'
import { listClientDebts, type Debt } from '../../entities/debt/api'
import { useCatalog } from '../../app/CatalogContext'
import {
  returnSale,
  getReceipt,
  getReceiptPdf,
  editSale,
  deleteSale,
  getSaleHistory,
  listSaleReturns,
  type PaymentMethod,
  type Sale,
  type SaleHistoryEntry,
  type SaleReturn,
} from '../../entities/sale/api'
import {
  IconReceiptRefund,
  IconUsers,
  IconChevronRight,
  IconCheck,
  IconBrandWhatsapp,
  IconDownload,
  IconShare,
  IconPencil,
  IconTrash,
  IconBuildingWarehouse,
  IconCoin,
  IconCash,
  IconCalendar,
  IconUser,
  type Icon as TablerIcon,
} from '@tabler/icons-react'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Select } from '../../shared/ui/Select'
import { HistoryDisclosure } from '../../shared/ui/HistoryDisclosure'
import {
  formatQuantity,
  formatMoney,
  normalizeDecimalInput,
} from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from '../../entities/debt/debtStatus'
import { useAuth } from '../../app/AuthContext'
import { PAYMENT_LABELS, PAYMENT_BADGE_CLASS } from './saleDraft'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './SalePage.module.css'
import detailStyles from './SaleDetailPage.module.css'

const SALE_HISTORY_ACTION_LABELS: Record<string, string> = {
  'sale.create': 'Продажа создана',
  'sale.return': 'Оформлен возврат',
  'sale.edit': 'Изменены данные продажи',
  'sale.delete': 'Продажа удалена',
}

const SALE_HISTORY_ACTION_ICONS: Record<string, TablerIcon> = {
  'sale.create': IconCheck,
  'sale.edit': IconPencil,
  'sale.delete': IconTrash,
  'sale.return': IconReceiptRefund,
}

function formatSaleHistoryDetail(entry: SaleHistoryEntry): string | null {
  const d = entry.details
  switch (entry.action) {
    case 'sale.create': {
      const method = d.payment_method as PaymentMethod | undefined
      return `${formatMoney(String(d.total ?? '0'))} ₽${method ? ` · ${PAYMENT_LABELS[method]}` : ''}`
    }
    case 'sale.return':
      return `Возврат на ${formatMoney(String(d.refund ?? '0'))} ₽`
    case 'sale.delete':
      return `Сумма продажи ${formatMoney(String(d.total ?? '0'))} ₽`
    default:
      return null
  }
}

export function SaleDetailView({
  sale: initialSale,
  warehouses,
  clients,
  onDone,
  onUpdated,
}: {
  sale: Sale
  warehouses: Warehouse[]
  clients: Client[]
  onDone: () => void
  onUpdated: () => void
}) {
  const { user } = useAuth()
  const {
    products,
    units,
    employees,
    ensureProducts,
    ensureUnits,
    ensureEmployees,
    refresh: refreshCatalog,
  } = useCatalog()
  const [sale, setSale] = useState(initialSale)
  const [returns, setReturns] = useState<SaleReturn[]>([])
  const [clientDebt, setClientDebt] = useState<Debt | null>(null)
  const [showReturn, setShowReturn] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showEdit, setShowEdit] = useState(false)
  const [quantities, setQuantities] = useState<Record<number, string>>(() =>
    Object.fromEntries(sale.lines.map((l) => [l.id, ''])),
  )
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [done, setDone] = useState(false)
  const [cashToClient, setCashToClient] = useState<string | null>(null)
  const [receiptError, setReceiptError] = useState<string | null>(null)
  const [sendingReceipt, setSendingReceipt] = useState(false)
  const [sharingReceipt, setSharingReceipt] = useState(false)
  const [downloadingReceipt, setDownloadingReceipt] = useState(false)
  const canShareFiles = typeof navigator.share === 'function' && typeof navigator.canShare === 'function'

  useEffect(() => {
    setSale(initialSale)
    setQuantities(Object.fromEntries(initialSale.lines.map((l) => [l.id, ''])))
  }, [initialSale])

  useEffect(() => {
    setDone(false)
    setCashToClient(null)
  }, [initialSale.id])

  useEffect(() => {
    ensureProducts().catch(() => {})
    ensureUnits().catch(() => {})
    ensureEmployees().catch(() => {})
    listSaleReturns(sale.id).then(setReturns).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sale.id])

  useEffect(() => {
    if (sale.payment_method !== 'credit' || sale.client_id == null) {
      setClientDebt(null)
      return
    }
    listClientDebts(sale.client_id)
      .then((summary) => setClientDebt(summary.debts.find((d) => d.sale_id === sale.id) ?? null))
      .catch(() => {})
  }, [sale.payment_method, sale.client_id, sale.id])

  const productName = (id: number) => products.find((p) => p.id === id)?.name ?? `Товар #${id}`
  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code
  const warehouseName = (id: number) => warehouses.find((w) => w.id === id)?.name ?? `#${id}`
  const client = sale.client_id != null ? clients.find((c) => c.id === sale.client_id) : null
  const seller = employees.find((e) => e.id === sale.seller_id)

  const alreadyReturned = (saleLineId: number) =>
    returns
      .flatMap((r) => r.lines)
      .filter((l) => l.sale_line_id === saleLineId)
      .reduce((sum, l) => sum + Number(l.quantity), 0)

  const totalRefunded = returns.reduce((sum, r) => sum + Number(r.refund), 0)

  const canDelete = user?.role === 'owner' || user?.role === 'manager'
  const isOwnSaleWithinWindow =
    user != null &&
    user.id === sale.seller_id &&
    Date.now() - new Date(sale.created_at).getTime() < 24 * 60 * 60 * 1000
  const canEdit = canDelete || isOwnSaleWithinWindow

  async function handleSendReceipt() {
    setReceiptError(null)
    setSendingReceipt(true)
    try {
      const receipt = await getReceipt(sale.id)
      if (receipt.whatsapp_link) {
        window.open(receipt.whatsapp_link, '_blank', 'noopener,noreferrer')
      } else {
        setReceiptError('У клиента не указан телефон/WhatsApp')
      }
    } catch (err) {
      setReceiptError(err instanceof ApiError ? err.message : 'Не удалось получить квитанцию')
    } finally {
      setSendingReceipt(false)
    }
  }

  async function handleDownloadReceipt() {
    setReceiptError(null)
    setDownloadingReceipt(true)
    try {
      const blob = await getReceiptPdf(sale.id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `chek-${sale.id}.pdf`
      link.click()
      URL.revokeObjectURL(url)

      const phone = client?.whatsapp || client?.phone
      if (phone) {
        window.open(`https://wa.me/${phone.replace(/\D/g, '')}`, '_blank', 'noopener,noreferrer')
      }
    } catch (err) {
      setReceiptError(err instanceof ApiError ? err.message : 'Не удалось получить квитанцию')
    } finally {
      setDownloadingReceipt(false)
    }
  }

  async function handleShareReceipt() {
    setReceiptError(null)
    setSharingReceipt(true)
    try {
      const blob = await getReceiptPdf(sale.id)
      const file = new File([blob], `chek-${sale.id}.pdf`, { type: 'application/pdf' })
      await navigator.share({ files: [file], title: `Чек №${sale.id}` })
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setReceiptError(err instanceof ApiError ? err.message : 'Не удалось получить квитанцию')
    } finally {
      setSharingReceipt(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const items = sale.lines
      .filter((l) => Number(quantities[l.id] || 0) > 0)
      .map((l) => ({ sale_line_id: l.id, quantity: quantities[l.id] }))
    if (items.length === 0) return
    setError(null)
    setSaving(true)
    try {
      const result = await returnSale(sale.id, { items })
      if (Number(result.cash_to_client ?? 0) > 0) {
        setCashToClient(result.cash_to_client ?? '0')
      } else {
        setCashToClient(null)
      }
      setDone(true)
      refreshCatalog(['stock']).catch(() => {})
      onUpdated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось оформить возврат')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    setError(null)
    try {
      await deleteSale(sale.id)
      refreshCatalog(['stock']).catch(() => {})
      onUpdated()
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось удалить продажу')
      setDeleting(false)
    }
  }

  if (done) {
    return (
      <div className={layoutStyles.stack}>
        <div className={layoutStyles.row} style={{ gap: 8 }}>
          <IconCheck size={18} stroke={1.8} className={styles.iconAccent} />
          <p>Возврат по продаже №{sale.id} оформлен, остаток восстановлен</p>
        </div>
        {cashToClient != null && Number(cashToClient) > 0 && (
          <p>
            Вернуть клиенту <strong>{formatMoney(cashToClient)} ₽</strong>
          </p>
        )}
        <Button onClick={onDone} style={{ alignSelf: 'flex-start' }}>К списку продаж</Button>
      </div>
    )
  }

  const headerActions = (
    <>
      <IconButton
        variant="muted"
        size="lg"
        onClick={handleSendReceipt}
        disabled={sendingReceipt}
        tooltip={
          sendingReceipt
            ? 'Открываем…'
            : client?.whatsapp || client?.phone
              ? `Отправить чек клиенту${client?.name ? ` (${client.name})` : ''}`
              : 'Отправить чек текстом'
        }
        aria-label="Отправить чек в WhatsApp"
      >
        <IconBrandWhatsapp size={22} stroke={1.8} />
      </IconButton>
      <IconButton
        variant="muted"
        size="lg"
        onClick={handleDownloadReceipt}
        disabled={downloadingReceipt}
        tooltip={
          downloadingReceipt
            ? 'Готовим…'
            : client?.whatsapp || client?.phone
              ? 'Скачать чек и открыть WhatsApp'
              : 'Скачать чек (PDF)'
        }
        aria-label="Скачать чек"
      >
        <IconDownload size={22} stroke={1.8} />
      </IconButton>
      {canShareFiles && (
        <IconButton
          variant="muted"
          size="lg"
          onClick={handleShareReceipt}
          disabled={sharingReceipt}
          tooltip={sharingReceipt ? 'Готовим…' : 'Поделиться'}
          aria-label="Поделиться чеком"
        >
          <IconShare size={22} stroke={1.8} />
        </IconButton>
      )}
    </>
  )

  return (
    <div className={layoutStyles.stack}>
      <section className={`${detailStyles.hero} ${detailStyles.reveal}`} style={{ '--reveal-delay': '0ms' } as CSSProperties}>
        <div className={detailStyles.heroBody}>
          <div className={detailStyles.heroTop}>
            <div className={detailStyles.heroHeading}>
              <h2 className={detailStyles.heroTitle}>Продажа №{sale.id}</h2>
              <div className={detailStyles.heroTags}>
                {sale.deleted_at ? (
                  <span className="badge danger">Удалена</span>
                ) : (
                  <span className={PAYMENT_BADGE_CLASS[sale.payment_method]}>
                    {PAYMENT_LABELS[sale.payment_method]}
                  </span>
                )}
                {sale.order_id != null && (
                  <Link to={`/orders/${sale.order_id}`} className="badge accent">
                    Из заказа №{sale.order_id}
                  </Link>
                )}
              </div>
            </div>
            <div className={styles.saleDetailActions}>
              {headerActions}
              {!sale.deleted_at && (
                <>
                  {canEdit && (
                    <IconButton
                      variant="muted"
                      size="lg"
                      onClick={() => setShowEdit(true)}
                      tooltip="Изменить продажу"
                      aria-label="Изменить продажу"
                    >
                      <IconPencil size={22} stroke={1.8} />
                    </IconButton>
                  )}
                  <IconButton
                    variant="muted"
                    size="lg"
                    onClick={() => setShowReturn(true)}
                    tooltip="Оформить возврат"
                    aria-label="Оформить возврат"
                  >
                    <IconReceiptRefund size={22} stroke={1.8} />
                  </IconButton>
                  {canDelete && (
                    <IconButton
                      variant="danger"
                      size="lg"
                      onClick={() => setShowDeleteConfirm(true)}
                      tooltip="Удалить продажу"
                      aria-label="Удалить продажу"
                    >
                      <IconTrash size={22} stroke={1.8} />
                    </IconButton>
                  )}
                </>
              )}
            </div>
          </div>
          <div className={detailStyles.heroPrice}>
            {formatMoney(sale.total)}
            <span className={detailStyles.heroPriceCurrency}>₽</span>
          </div>
          <div className={detailStyles.heroMeta}>
            <span>
              <IconCalendar size={15} stroke={1.8} />
              {new Date(sale.created_at).toLocaleString('ru-RU', {
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
            <span>
              <IconBuildingWarehouse size={15} stroke={1.8} />
              {warehouseName(sale.warehouse_id)}
            </span>
            <span>
              <IconUser size={15} stroke={1.8} />
              {seller ? seller.name : `#${sale.seller_id}`}
            </span>
          </div>
        </div>
      </section>

      {(receiptError || error) && <p className={layoutStyles.error}>{receiptError || error}</p>}

      <section
        className={`${detailStyles.metrics} ${detailStyles.reveal}`}
        style={{ '--reveal-delay': '60ms' } as CSSProperties}
      >
        <div className={detailStyles.metric}>
          <span className={detailStyles.metricIcon}>
            <IconCoin size={18} stroke={1.8} />
          </span>
          <div className={detailStyles.metricBody}>
            <strong>
              {formatMoney(sale.total)}
              <span className={detailStyles.metricCurrency}> ₽</span>
            </strong>
            <span>Итого</span>
          </div>
        </div>
        <div className={detailStyles.metric}>
          <span className={detailStyles.metricIcon}>
            <IconCash size={18} stroke={1.8} />
          </span>
          <div className={detailStyles.metricBody}>
            <strong>{PAYMENT_LABELS[sale.payment_method]}</strong>
            <span>Оплата</span>
          </div>
        </div>
        {sale.payment_method === 'cash' && (
          <>
            <div className={detailStyles.metric}>
              <span className={detailStyles.metricIcon}>
                <IconCash size={18} stroke={1.8} />
              </span>
              <div className={detailStyles.metricBody}>
                <strong>
                  {sale.cash_received != null ? (
                    <>
                      {formatMoney(sale.cash_received)}
                      <span className={detailStyles.metricCurrency}> ₽</span>
                    </>
                  ) : (
                    '—'
                  )}
                </strong>
                <span>Внесено</span>
              </div>
            </div>
            <div className={detailStyles.metric}>
              <span className={detailStyles.metricIcon}>
                <IconCoin size={18} stroke={1.8} />
              </span>
              <div className={detailStyles.metricBody}>
                <strong>
                  {sale.change != null ? (
                    <>
                      {formatMoney(sale.change)}
                      <span className={detailStyles.metricCurrency}> ₽</span>
                    </>
                  ) : (
                    '—'
                  )}
                </strong>
                <span>Сдача выдана</span>
              </div>
            </div>
            {Number(sale.change_kept ?? 0) > 0 && (
              <div className={detailStyles.metric}>
                <span className={detailStyles.metricIcon}>
                  <IconCoin size={18} stroke={1.8} />
                </span>
                <div className={detailStyles.metricBody}>
                  <strong>
                    {formatMoney(sale.change_kept ?? 0)}
                    <span className={detailStyles.metricCurrency}> ₽</span>
                  </strong>
                  <span>Не взяли сдачу</span>
                </div>
              </div>
            )}
          </>
        )}
        <div className={detailStyles.metric}>
          <span className={detailStyles.metricIcon}>
            <IconBuildingWarehouse size={18} stroke={1.8} />
          </span>
          <div className={detailStyles.metricBody}>
            <strong>{warehouseName(sale.warehouse_id)}</strong>
            <span>Склад</span>
          </div>
        </div>
      </section>

      {client && (
        <div className={styles.saleDetailClientCard}>
          <Link to={`/clients/${client.id}`} className={styles.saleDetailClientLink}>
            <IconUsers size={16} stroke={1.8} />
            <span className={styles.saleDetailClientName}>{client.name}</span>
          </Link>
          {clientDebt && !clientDebt.is_closed && (
            <Link
              to={`/debts?highlight=${clientDebt.id}`}
              className={DEBT_STATUS_BADGE_CLASS[clientDebt.status]}
            >
              {formatMoney(clientDebt.balance)} ₽
              {clientDebt.due_date &&
                ` · до ${new Date(clientDebt.due_date).toLocaleDateString('ru-RU')}`}
              {' · '}
              {DEBT_STATUS_LABELS[clientDebt.status]}
            </Link>
          )}
          {clientDebt && clientDebt.is_closed && (
            <span className="badge accent">Долг погашен</span>
          )}
          <Link to={`/clients/${client.id}`} className={styles.saleDetailClientArrowLink}>
            <IconChevronRight size={16} stroke={1.8} className={styles.saleDetailClientArrow} />
          </Link>
        </div>
      )}

      {returns.length > 0 && (
        <p className={layoutStyles.textMuted}>
          Возвращено: {formatMoney(totalRefunded)} ₽
          {returns
            .map((r) => r.note.trim())
            .filter(Boolean)
            .map((note, i) => (
              <span key={i}> · {note}</span>
            ))}
        </p>
      )}

      <section className={`${detailStyles.section} ${detailStyles.reveal}`} style={{ '--reveal-delay': '110ms' } as CSSProperties}>
      <h3 className={detailStyles.sectionTitle}>
        Товары <span className={layoutStyles.textMuted}>· {sale.lines.length} поз.</span>
      </h3>

      <div className={styles.saleLineList}>
        {sale.lines.map((line, i) => (
          <div
            key={line.id}
            className={[styles.saleLineRow, styles.saleHistoryRowIn].join(' ')}
            style={{ '--row-delay': `${Math.min(i, 12) * 25}ms` } as CSSProperties}
          >
            <span className={styles.saleLineName}>{productName(line.product_id)}</span>
            <span className={styles.saleLineMeta}>
              {formatQuantity(line.quantity)} {unitName(products.find((p) => p.id === line.product_id)?.unit_code ?? '')}
              {' × '}
              {formatMoney(line.price)} ₽
            </span>
            <span className={styles.saleLineTotal}>{formatMoney(line.total)} ₽</span>
          </div>
        ))}
      </div>

      <div className="sale-detail-totals">
        {Number(sale.discount) > 0 && (
          <>
            <div className="sale-detail-totals-row">
              <span>Товары</span>
              <span>{formatMoney(sale.subtotal)} ₽</span>
            </div>
            <div className="sale-detail-totals-row">
              <span>{sale.order_id != null ? 'Предоплата по заказу' : 'Скидка'}</span>
              <span>−{formatMoney(sale.discount)} ₽</span>
            </div>
          </>
        )}
        <div className="sale-detail-totals-row sale-detail-totals-row-sum">
          <span>Итого</span>
          <span>{formatMoney(sale.total)} ₽</span>
        </div>
        {sale.payment_method === 'credit' && Number(sale.paid_now ?? 0) > 0 && (
          <>
            <div className="sale-detail-totals-row">
              <span>Оплачено сразу</span>
              <span>{formatMoney(sale.paid_now ?? 0)} ₽</span>
            </div>
            <div className="sale-detail-totals-row">
              <span>В долг</span>
              <span>{formatMoney(sale.debt_amount ?? sale.total)} ₽</span>
            </div>
          </>
        )}
      </div>

      </section>

      <SaleNoteEditor sale={sale} canEdit={canEdit} onSaved={setSale} />

      <HistoryDisclosure
        load={() => getSaleHistory(sale.id)}
        actionLabels={SALE_HISTORY_ACTION_LABELS}
        actionIcons={SALE_HISTORY_ACTION_ICONS}
        formatDetail={formatSaleHistoryDetail}
      />

      {showReturn && (
        <Modal title={`Возврат по продаже №${sale.id}`} onClose={() => setShowReturn(false)}>
          <form className={layoutStyles.form} onSubmit={handleSubmit}>
            {sale.lines.map((line) => {
              const remaining = Number(line.quantity) - alreadyReturned(line.id)
              return (
                <label className={layoutStyles.field} key={line.id}>
                  {productName(line.product_id)} (доступно к возврату: {formatQuantity(remaining)})
                  <input
                    type="text"
                    inputMode="decimal"
                    placeholder="0"
                    disabled={remaining <= 0}
                    value={quantities[line.id]}
                    onChange={(e) => {
                      const normalized = normalizeDecimalInput(e.target.value)
                      if (normalized !== null) {
                        setQuantities((prev) => ({ ...prev, [line.id]: normalized }))
                      }
                    }}
                  />
                </label>
              )
            })}
            {error && <p className={layoutStyles.error}>{error}</p>}
            <Button type="submit" disabled={saving}>
              {saving ? 'Оформление…' : 'Вернуть товар'}
            </Button>
          </form>
        </Modal>
      )}

      {showEdit && (
        <Modal title={`Изменить продажу №${sale.id}`} onClose={() => setShowEdit(false)}>
          <SaleEditForm
            sale={sale}
            clients={clients}
            onSaved={(updated) => {
              setSale(updated)
              setShowEdit(false)
              onUpdated()
            }}
          />
        </Modal>
      )}

      {showDeleteConfirm && (
        <Modal title="Удалить продажу?" onClose={() => setShowDeleteConfirm(false)}>
          <div className={layoutStyles.stack}>
            <p>
              Продажа №{sale.id} будет удалена: все проданные товары вернутся на склад
              {sale.payment_method === 'credit' && ', а связанный долг клиента будет аннулирован'}.
              Это действие нельзя отменить.
            </p>
            {error && <p className={layoutStyles.error}>{error}</p>}
            <div className={layoutStyles.row} style={{ gap: 8 }}>
              <Button variant="danger" onClick={handleDelete} disabled={deleting}>
                {deleting ? 'Удаление…' : 'Да, удалить'}
              </Button>
              <Button variant="secondary" onClick={() => setShowDeleteConfirm(false)}>
                Отмена
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

function SaleNoteEditor({
  sale,
  canEdit,
  onSaved,
}: {
  sale: Sale
  canEdit: boolean
  onSaved: (sale: Sale) => void
}) {
  const [note, setNote] = useState(sale.note)
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const saveTimerRef = useRef<number | undefined>(undefined)
  const savedTimerRef = useRef<number | undefined>(undefined)
  const noteRef = useRef(note)
  noteRef.current = note

  useEffect(
    () => () => {
      window.clearTimeout(saveTimerRef.current)
      window.clearTimeout(savedTimerRef.current)
    },
    [],
  )

  async function saveNote(value: string) {
    setStatus('saving')
    try {
      const updated = await editSale(sale.id, { client_id: sale.client_id, note: value })
      onSaved(updated)
      setStatus('saved')
      window.clearTimeout(savedTimerRef.current)
      savedTimerRef.current = window.setTimeout(() => setStatus('idle'), 2000)
    } catch {
      setStatus('error')
    }
  }

  function handleChange(value: string) {
    setNote(value)
    window.clearTimeout(saveTimerRef.current)
    saveTimerRef.current = window.setTimeout(() => saveNote(noteRef.current), 800)
  }

  return (
    <div className={styles.saleNote}>
      <div className={styles.saleNoteHeader}>
        <span className={styles.saleNoteTitle}>Заметка к продаже</span>
        <span
          className={[
            styles.saleNoteStatus,
            status === 'idle' && styles.saleNoteStatusHidden,
            status === 'error' && styles.saleNoteStatusError,
          ]
            .filter(Boolean)
            .join(' ')}
        >
          {status === 'saving' && 'Сохранение…'}
          {status === 'saved' && (
            <>
              <IconCheck size={12} stroke={1.8} /> Сохранено
            </>
          )}
          {status === 'error' && 'Не удалось сохранить'}
        </span>
      </div>
      <textarea
        className={styles.saleNoteTextarea}
        rows={2}
        value={note}
        disabled={!canEdit}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={canEdit ? 'Например: заберёт завтра, оплата через терминал…' : 'Нет заметки'}
      />
    </div>
  )
}

function SaleEditForm({
  sale,
  clients,
  onSaved,
}: {
  sale: Sale
  clients: Client[]
  onSaved: (sale: Sale) => void
}) {
  const [clientId, setClientId] = useState<number | null>(sale.client_id)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const updated = await editSale(sale.id, { client_id: clientId, note: sale.note })
      onSaved(updated)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить изменения')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={layoutStyles.form} onSubmit={handleSubmit}>
      <label className={layoutStyles.field}>
        Клиент
        <Select
          value={String(clientId ?? '')}
          onChange={(v) => setClientId(v ? Number(v) : null)}
          options={[
            { value: '', label: 'Без клиента' },
            ...clients.map((c) => ({ value: String(c.id), label: c.name })),
          ]}
        />
      </label>
      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Сохранить'}
      </Button>
    </form>
  )
}

