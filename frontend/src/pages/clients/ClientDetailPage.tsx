import { useEffect, useMemo, useState, type CSSProperties, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  IconChevronLeft,
  IconChevronRight,
  IconUser,
  IconPhone,
  IconMapPin,
  IconShieldCheck,
  IconShieldExclamation,
  IconShieldQuestion,
  IconReceipt2,
  IconWallet,
  IconClockHour4,
  IconCash,
  IconCalendarRepeat,
  IconPencil,
} from '@tabler/icons-react'
import { searchClients, updateClient, getClient, getClientTimeline, type Client, type ClientTimelineEvent, type ClientSummary } from '../../entities/counterparty/api'
import { listClientDebts, type Debt } from '../../entities/debt/api'
import { DebtCard } from '../../entities/debt/DebtCard'
import { listSales, getSale, type Sale } from '../../entities/sale/api'
import { listDocuments, type DocumentHistoryEntry } from '../../entities/inventory/api'
import { useCatalog } from '../../app/CatalogContext'
import { ApiError } from '../../shared/api/client'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Modal } from '../../shared/ui/Modal'
import { PhoneInput } from '../../shared/ui/PhoneInput'
import { formatMoney, normalizeDecimalInput } from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from '../../entities/debt/debtStatus'
import { daysOverdue, pluralDays } from '../../entities/debt/dueDate'
import layoutStyles from '../../shared/ui/Layout.module.css'
import debtsStyles from '../debts/DebtsPage.module.css'
import styles from './ClientDetailPage.module.css'

const DEBT_STATUS_ACCENT: Record<Debt['status'], string> = {
  active: 'var(--border)',
  due_soon: 'var(--warning)',
  overdue: 'var(--danger)',
  partially_paid: 'var(--warning)',
  closed: 'var(--accent)',
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('ru-RU')
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

type Reputation = {
  level: 'new' | 'good' | 'risky' | 'bad'
  label: string
  hint: string
}

// Репутация считается на фронте из уже загруженных долгов клиента — без
// отдельного бэкенд-эндпоинта: смотрим, сколько долгов закрыто без просрочки
// и есть ли активная просрочка прямо сейчас.
function computeReputation(debts: Debt[]): Reputation {
  if (debts.length === 0) {
    return { level: 'new', label: 'Новый клиент', hint: 'Ещё не было долгов' }
  }
  const activeOverdue = debts.filter((d) => !d.is_closed && d.status === 'overdue')
  const closed = debts.filter((d) => d.is_closed)
  const closedLate = closed.filter((d) => d.due_date && new Date(d.due_date) < new Date())

  if (activeOverdue.length > 0) {
    return {
      level: 'bad',
      label: 'Есть просрочка',
      hint: `Просрочено долгов: ${activeOverdue.length}`,
    }
  }
  if (closed.length === 0) {
    return { level: 'new', label: 'Пока без истории', hint: 'Долги ещё не закрывались' }
  }
  if (closedLate.length / closed.length > 0.3) {
    return {
      level: 'risky',
      label: 'Платит с задержками',
      hint: `Просрочек в прошлом: ${closedLate.length} из ${closed.length}`,
    }
  }
  return {
    level: 'good',
    label: 'Надёжный клиент',
    hint: `Закрыл в срок ${closed.length - closedLate.length} из ${closed.length} долгов`,
  }
}

const REPUTATION_ICON: Record<Reputation['level'], typeof IconShieldCheck> = {
  new: IconShieldQuestion,
  good: IconShieldCheck,
  risky: IconShieldExclamation,
  bad: IconShieldExclamation,
}

export function ClientDetailPage() {
  const { id } = useParams<{ id: string }>()
  const clientId = Number(id)
  const { products: debtProducts, units: debtUnits, ensureProducts, ensureUnits } = useCatalog()

  const [client, setClient] = useState<Client | null>(null)
  const [summary, setSummary] = useState<ClientSummary | null>(null)
  const [debts, setDebts] = useState<Debt[] | null>(null)
  const [sales, setSales] = useState<Sale[] | null>(null)
  const [timeline, setTimeline] = useState<ClientTimelineEvent[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<'debts' | 'sales' | 'history'>('debts')
  const [showEdit, setShowEdit] = useState(false)
  const [openDebtId, setOpenDebtId] = useState<number | null>(null)
  const [debtSale, setDebtSale] = useState<Sale | null>(null)
  const [debtReceipt, setDebtReceipt] = useState<DocumentHistoryEntry | null>(null)
  const [debtLoading, setDebtLoading] = useState(false)

  async function openDebt(debtId: number) {
    setOpenDebtId(debtId)
    setDebtLoading(true)
    const target = (debts ?? []).find((d) => d.id === debtId)
    try {
      if (target?.sale_id != null) {
        const [s] = await Promise.all([getSale(target.sale_id), ensureProducts(), ensureUnits()])
        setDebtSale(s)
        setDebtReceipt(null)
      } else if (target?.receipt_document_id != null) {
        const [documents] = await Promise.all([listDocuments(), ensureProducts(), ensureUnits()])
        setDebtSale(null)
        setDebtReceipt(documents.find((doc) => doc.id === target.receipt_document_id) ?? null)
      } else {
        setDebtSale(null)
        setDebtReceipt(null)
      }
    } finally {
      setDebtLoading(false)
    }
  }

  async function reloadOpenDebt() {
    const debtsSummary = await listClientDebts(clientId)
    setDebts(debtsSummary.debts)
  }

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const [summaryData, debtsSummary, salesResult, timelineData] = await Promise.all([
          getClient(clientId),
          listClientDebts(clientId),
          listSales({ clientId, limit: 200 }),
          getClientTimeline(clientId),
        ])
        if (cancelled) return
        setSummary(summaryData)
        setClient(summaryData.client)
        setDebts(debtsSummary.debts)
        setSales(salesResult.items)
        setTimeline(timelineData)
      } catch (err) {
        if (!cancelled) {
          // fallback: старый путь через поиск, если summary недоступен
          try {
            const [clients, debtsSummary, salesResult] = await Promise.all([
              searchClients('', true),
              listClientDebts(clientId),
              listSales({ clientId, limit: 200 }),
            ])
            if (cancelled) return
            setClient(clients.find((c) => c.id === clientId) ?? null)
            setDebts(debtsSummary.debts)
            setSales(salesResult.items)
          } catch (fallbackErr) {
            setError(
              fallbackErr instanceof ApiError
                ? fallbackErr.message
                : err instanceof ApiError
                  ? err.message
                  : 'Не удалось загрузить клиента',
            )
          }
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [clientId])

  const activeDebts = useMemo(() => (debts ?? []).filter((d) => !d.is_closed), [debts])
  const closedDebts = useMemo(() => (debts ?? []).filter((d) => d.is_closed), [debts])
  const totalBalance = useMemo(
    () =>
      summary
        ? Number(summary.debt_balance)
        : activeDebts.reduce((sum, d) => sum + Number(d.balance), 0),
    [summary, activeDebts],
  )
  const totalPurchased = useMemo(
    () => (sales ?? []).reduce((sum, s) => sum + Number(s.total), 0),
    [sales],
  )
  const reputation = useMemo(() => computeReputation(debts ?? []), [debts])
  const ReputationIcon = REPUTATION_ICON[reputation.level]

  if (!loading && !client) {
    return (
      <div className={layoutStyles.stack}>
        <Link to="/clients" className={layoutStyles.backLink}>
          <IconChevronLeft size={16} stroke={1.8} /> Все контрагенты
        </Link>
        <p className={layoutStyles.error}>{error ?? 'Клиент не найден'}</p>
      </div>
    )
  }

  return (
    <div className={layoutStyles.stack}>
      <Link to="/clients" className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> Все контрагенты
      </Link>

      {!client ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : (
        <>
          <div className={styles['client-detail-header']}>
            <span className={styles['client-detail-avatar']}>
              <IconUser size={22} stroke={1.8} />
            </span>
            <div className={styles['client-detail-heading']}>
              <div className={layoutStyles.row} style={{ gap: 6 }}>
                <h2>{client.name}</h2>
                {!client.is_active && <span className="badge">Неактивен</span>}
                <IconButton
                  variant="muted"
                  tooltip="Изменить клиента"
                  aria-label="Изменить клиента"
                  onClick={() => setShowEdit(true)}
                >
                  <IconPencil size={16} stroke={1.8} />
                </IconButton>
              </div>
              <div className={styles['client-detail-contacts']}>
                {client.phone && (
                  <span>
                    <IconPhone size={13} stroke={1.8} /> {client.phone}
                  </span>
                )}
                {client.city && (
                  <span>
                    <IconMapPin size={13} stroke={1.8} /> {client.city}
                  </span>
                )}
                {client.debt_limit && <span>Лимит долга: {formatMoney(client.debt_limit)} ₽</span>}
              </div>
            </div>
            <div className={`${styles['client-reputation']} ${styles[`client-reputation-${reputation.level}`]}`}>
              <ReputationIcon size={18} stroke={1.8} />
              <div className={styles['client-reputation-text']}>
                <strong>{reputation.label}</strong>
                <span>{reputation.hint}</span>
              </div>
            </div>
          </div>

          <div className={styles['client-metrics']}>
            <div className={styles['client-metric']}>
              <span className={styles['client-metric-icon']}>
                <IconWallet size={16} stroke={1.8} />
              </span>
              <div className={styles['client-metric-body']}>
                <strong>{formatMoney(totalBalance)} ₽</strong>
                <span>Долг сейчас{activeDebts.length > 0 ? ` · ${activeDebts.length} шт.` : ''}</span>
              </div>
            </div>
            <div className={styles['client-metric']}>
              <span className={styles['client-metric-icon']}>
                <IconReceipt2 size={16} stroke={1.8} />
              </span>
              <div className={styles['client-metric-body']}>
                <strong>{formatMoney(totalPurchased)} ₽</strong>
                <span>Куплено всего{sales ? ` · ${sales.length} продаж` : ''}</span>
              </div>
            </div>
            <div className={styles['client-metric']}>
              <span className={styles['client-metric-icon']}>
                <IconClockHour4 size={16} stroke={1.8} />
              </span>
              <div className={styles['client-metric-body']}>
                <strong>{closedDebts.length}</strong>
                <span>Долгов закрыто</span>
              </div>
            </div>
            {summary && (
              <>
                <div className={styles['client-metric']}>
                  <span className={styles['client-metric-icon']}>
                    <IconCalendarRepeat size={16} stroke={1.8} />
                  </span>
                  <div className={styles['client-metric-body']}>
                    <strong>{summary.active_orders_count}</strong>
                    <span>Активных заказов</span>
                  </div>
                </div>
                <div className={styles['client-metric']}>
                  <span className={styles['client-metric-icon']}>
                    <IconShieldCheck size={16} stroke={1.8} />
                  </span>
                  <div className={styles['client-metric-body']}>
                    <strong>{summary.open_tasks_count}</strong>
                    <span>Открытых задач</span>
                  </div>
                </div>
              </>
            )}
          </div>

          <div className="sale-period-tabs">
            <Button variant="secondary" active={tab === 'debts'} onClick={() => setTab('debts')}>
              Долги{debts && debts.length > 0 && <span className={layoutStyles.countBadge}>{debts.length}</span>}
            </Button>
            <Button variant="secondary" active={tab === 'sales'} onClick={() => setTab('sales')}>
              Покупки{sales && sales.length > 0 && <span className={layoutStyles.countBadge}>{sales.length}</span>}
            </Button>
            <Button variant="secondary" active={tab === 'history'} onClick={() => setTab('history')}>
              История
            </Button>
          </div>

          {error && <p className={layoutStyles.error}>{error}</p>}

          {tab === 'debts' &&
            (debts === null ? (
              <p className={layoutStyles.textMuted}>Загрузка…</p>
            ) : debts.length === 0 ? (
              <p className={layoutStyles.textMuted}>Долгов пока нет</p>
            ) : (
              <div className={layoutStyles.stack} style={{ gap: 16 }}>
                <div className={debtsStyles['debt-closed-group']}>
                  <div className={debtsStyles['debt-closed-group-head']}>
                    Текущие долги{activeDebts.length > 0 ? ` · ${activeDebts.length}` : ''}
                  </div>
                  {activeDebts.length === 0 ? (
                    <p className={layoutStyles.textMuted}>Активных долгов нет</p>
                  ) : (
                    <div className={debtsStyles['debt-row-list']}>
                      {activeDebts.map((d) => (
                        <DebtRow key={d.id} debt={d} onClick={() => openDebt(d.id)} />
                      ))}
                    </div>
                  )}
                </div>
                {closedDebts.length > 0 && (
                  <div className={debtsStyles['debt-closed-group']}>
                    <div className={debtsStyles['debt-closed-group-head']}>Погашенные · {closedDebts.length}</div>
                    <div className={debtsStyles['debt-row-list']}>
                      {closedDebts.map((d) => (
                        <DebtRow key={d.id} debt={d} onClick={() => openDebt(d.id)} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}

          {tab === 'sales' &&
            (sales === null ? (
              <p className={layoutStyles.textMuted}>Загрузка…</p>
            ) : sales.length === 0 ? (
              <p className={layoutStyles.textMuted}>Покупок пока нет</p>
            ) : (
              <div className={layoutStyles.dataTable}>
                <div className={layoutStyles.dataTableHead} style={{ gridTemplateColumns: '1fr 1fr 1fr 20px' }}>
                  <span>Дата</span>
                  <span>Сумма</span>
                  <span>Оплата</span>
                  <span />
                </div>
                <div className={layoutStyles.dataTableBody}>
                  {sales.map((s) => (
                    <div key={s.id} className={layoutStyles.dataRow} style={{ gridTemplateColumns: '1fr 1fr 1fr 20px' }}>
                      <span className={layoutStyles.textMuted}>{formatDateTime(s.created_at)}</span>
                      <span className={layoutStyles.dataRowName}>{formatMoney(s.total)} ₽</span>
                      <span className={layoutStyles.textMuted}>
                        {s.payment_method === 'cash' ? 'Наличные' : s.payment_method === 'transfer' ? 'Перевод' : 'В долг'}
                      </span>
                      <span />
                    </div>
                  ))}
                </div>
              </div>
            ))}

          {tab === 'history' &&
            (timeline === null ? (
              <p className={layoutStyles.textMuted}>Загрузка…</p>
            ) : timeline.length === 0 ? (
              <p className={layoutStyles.textMuted}>Событий пока нет</p>
            ) : (
              <div className={styles['client-history-list']}>
                {timeline.map((ev, i) => {
                  const Icon =
                    ev.type === 'sale'
                      ? IconReceipt2
                      : ev.type === 'debt_repaid'
                        ? IconCash
                        : ev.type === 'task'
                          ? IconShieldCheck
                          : IconCalendarRepeat
                  const debtClickable =
                    ev.type === 'debt_issued' || ev.type === 'debt_repaid' || ev.type === 'debt_extended'
                  const content = (
                    <>
                      <span className={styles['client-history-icon']}>
                        <Icon size={14} stroke={1.8} />
                      </span>
                      <div className={styles['client-history-body']}>
                        <span>
                          {ev.title}
                          {ev.amount != null && <> · {formatMoney(ev.amount)} ₽</>}
                        </span>
                        <span className={layoutStyles.textMuted}>{formatDateTime(ev.occurred_at)}</span>
                      </div>
                      {(debtClickable || ev.type === 'sale') && (
                        <IconChevronRight size={16} stroke={1.8} className={layoutStyles.dataRowChevron} />
                      )}
                    </>
                  )
                  if (ev.type === 'sale') {
                    return (
                      <Link
                        key={`${ev.type}-${ev.entity_id}-${i}`}
                        to={`/?openSale=${ev.entity_id}`}
                        className={`${styles['client-history-row']} ${styles['client-history-row-link']}`}
                      >
                        {content}
                      </Link>
                    )
                  }
                  return (
                    <div
                      key={`${ev.type}-${ev.entity_id}-${i}`}
                      className={[
                        styles['client-history-row'],
                        debtClickable && styles['client-history-row-link'],
                      ]
                        .filter(Boolean)
                        .join(' ')}
                      role={debtClickable ? 'button' : undefined}
                      tabIndex={debtClickable ? 0 : undefined}
                      onClick={debtClickable ? () => openDebt(ev.entity_id) : undefined}
                    >
                      {content}
                    </div>
                  )
                })}
              </div>
            ))}
        </>
      )}

      {openDebtId != null && (
        <Modal title="Долг" onClose={() => setOpenDebtId(null)}>
          {debtLoading ? (
            <p className={layoutStyles.textMuted}>Загрузка…</p>
          ) : (
            (() => {
              const openDebtEntity = (debts ?? []).find((d) => d.id === openDebtId)
              return openDebtEntity ? (
                <DebtCard
                  debt={openDebtEntity}
                  clients={client ? [client] : []}
                  suppliers={[]}
                  sale={debtSale}
                  receiptDocument={debtReceipt}
                  products={debtProducts}
                  units={debtUnits}
                  onReload={reloadOpenDebt}
                  showHeader={false}
                />
              ) : (
                <p className={layoutStyles.error}>Долг не найден</p>
              )
            })()
          )}
        </Modal>
      )}

      {showEdit && client && (
        <Modal title="Изменить клиента" onClose={() => setShowEdit(false)}>
          <EditClientForm
            client={client}
            onDone={(updated) => {
              setShowEdit(false)
              setClient(updated)
            }}
          />
        </Modal>
      )}
    </div>
  )
}

function EditClientForm({ client, onDone }: { client: Client; onDone: (updated: Client) => void }) {
  const [name, setName] = useState(client.name)
  const [phone, setPhone] = useState(client.phone)
  const [city, setCity] = useState(client.city)
  const [debtLimit, setDebtLimit] = useState(client.debt_limit ?? '')
  const [isActive, setIsActive] = useState(client.is_active)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const updated = await updateClient(client.id, {
        name,
        phone,
        city,
        debt_limit: debtLimit || null,
        is_active: isActive,
      })
      onDone(updated)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить клиента')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={layoutStyles.form} onSubmit={handleSubmit}>
      <label className={layoutStyles.field}>
        Имя
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className={layoutStyles.field}>
        Телефон
        <PhoneInput value={phone} onChange={setPhone} />
      </label>
      <label className={layoutStyles.field}>
        Город
        <input value={city} onChange={(e) => setCity(e.target.value)} />
      </label>
      <label className={layoutStyles.field}>
        Лимит долга
        <input
          type="text"
          inputMode="decimal"
          value={debtLimit}
          onChange={(e) => {
            const normalized = normalizeDecimalInput(e.target.value)
            if (normalized !== null) setDebtLimit(normalized)
          }}
        />
      </label>
      <label className={layoutStyles.row} style={{ gap: 8 }}>
        <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
        Активен
      </label>
      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Сохранить'}
      </Button>
    </form>
  )
}

function DebtRow({ debt, onClick }: { debt: Debt; onClick: () => void }) {
  return (
    <button
      type="button"
      className={debtsStyles['debt-row']}
      style={{ '--debt-accent': DEBT_STATUS_ACCENT[debt.status] } as CSSProperties}
      onClick={onClick}
    >
      <span className={debtsStyles['debt-row-icon']}>
        <IconUser size={16} stroke={1.8} />
      </span>
      <div className={debtsStyles['debt-row-main']}>
        <div className={debtsStyles['debt-row-top']}>
          <span className={debtsStyles['debt-row-name']}>{formatDate(debt.issued_at)}</span>
          <strong>{formatMoney(debt.balance)} ₽</strong>
          <span className={DEBT_STATUS_BADGE_CLASS[debt.status]}>{DEBT_STATUS_LABELS[debt.status]}</span>
        </div>
        <div className={debtsStyles['debt-row-meta']}>
          <span>Остаток из {formatMoney(debt.amount)} ₽</span>
          {debt.due_date && !debt.is_closed && (
            <span className={daysOverdue(debt.due_date) > 0 ? layoutStyles.textDanger : undefined}>
              {daysOverdue(debt.due_date) > 0
                ? `Просрочен на ${daysOverdue(debt.due_date)} ${pluralDays(daysOverdue(debt.due_date))}`
                : `Срок до ${formatDate(debt.due_date)}`}
            </span>
          )}
        </div>
      </div>
      <IconChevronRight size={18} stroke={1.8} className={debtsStyles['debt-row-chevron']} />
    </button>
  )
}
