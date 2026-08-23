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
import { searchClients, updateClient, type Client } from '../../entities/counterparty/api'
import { listClientDebts, type Debt } from '../../entities/debt/api'
import { DebtCard } from '../../entities/debt/DebtCard'
import { listSales, getSale, type Sale } from '../../entities/sale/api'
import { listDocuments, type DocumentHistoryEntry } from '../../entities/inventory/api'
import { listAllProducts, listUnits, type Product, type Unit } from '../../entities/product/api'
import { ApiError } from '../../shared/api/client'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Modal } from '../../shared/ui/Modal'
import { PhoneInput } from '../../shared/ui/PhoneInput'
import { formatMoney, normalizeDecimalInput } from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from '../../entities/debt/debtStatus'
import { daysOverdue, pluralDays } from '../../entities/debt/dueDate'

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

  const [client, setClient] = useState<Client | null>(null)
  const [debts, setDebts] = useState<Debt[] | null>(null)
  const [sales, setSales] = useState<Sale[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<'debts' | 'sales' | 'history'>('debts')
  const [showEdit, setShowEdit] = useState(false)
  const [openDebtId, setOpenDebtId] = useState<number | null>(null)
  const [debtSale, setDebtSale] = useState<Sale | null>(null)
  const [debtReceipt, setDebtReceipt] = useState<DocumentHistoryEntry | null>(null)
  const [debtProducts, setDebtProducts] = useState<Product[]>([])
  const [debtUnits, setDebtUnits] = useState<Unit[]>([])
  const [debtLoading, setDebtLoading] = useState(false)

  async function loadClient() {
    const clients = await searchClients('', true)
    setClient(clients.find((c) => c.id === clientId) ?? null)
  }

  async function openDebt(debtId: number) {
    setOpenDebtId(debtId)
    setDebtLoading(true)
    const target = (debts ?? []).find((d) => d.id === debtId)
    try {
      if (target?.sale_id != null) {
        const [s, productList, unitList] = await Promise.all([
          getSale(target.sale_id),
          listAllProducts(),
          listUnits(),
        ])
        setDebtSale(s)
        setDebtReceipt(null)
        setDebtProducts(productList)
        setDebtUnits(unitList)
      } else if (target?.receipt_document_id != null) {
        const [documents, productList, unitList] = await Promise.all([
          listDocuments(),
          listAllProducts(),
          listUnits(),
        ])
        setDebtSale(null)
        setDebtReceipt(documents.find((doc) => doc.id === target.receipt_document_id) ?? null)
        setDebtProducts(productList)
        setDebtUnits(unitList)
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
        const [clients, debtsSummary, salesList] = await Promise.all([
          searchClients('', true),
          listClientDebts(clientId),
          listSales(),
        ])
        if (cancelled) return
        setClient(clients.find((c) => c.id === clientId) ?? null)
        setDebts(debtsSummary.debts)
        setSales(salesList.filter((s) => s.client_id === clientId))
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Не удалось загрузить клиента')
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
    () => activeDebts.reduce((sum, d) => sum + Number(d.balance), 0),
    [activeDebts],
  )
  const totalPurchased = useMemo(
    () => (sales ?? []).reduce((sum, s) => sum + Number(s.total), 0),
    [sales],
  )
  const reputation = useMemo(() => computeReputation(debts ?? []), [debts])
  const ReputationIcon = REPUTATION_ICON[reputation.level]

  // Единая лента событий клиента — долги (выдача/оплата/продление) и продажи,
  // слитые из уже загруженных данных и отсортированные по времени. Отдельного
  // бэкенд-эндпоинта для этого нет: всё собирается из debts.repayments/extensions
  // (они уже приходят вместе с долгом) и списка продаж.
  type HistoryEvent = {
    at: string
    kind: 'issue' | 'repay' | 'extend' | 'sale'
    amount?: string
    note?: string
    debtId?: number
    saleId?: number
  }
  const history = useMemo(() => {
    const events: HistoryEvent[] = []
    for (const d of debts ?? []) {
      events.push({ at: d.issued_at, kind: 'issue', amount: d.amount, debtId: d.id })
      for (const r of d.repayments)
        events.push({ at: r.on, kind: 'repay', amount: r.amount, note: r.note, debtId: d.id })
      for (const e of d.extensions)
        events.push({
          at: e.created_at,
          kind: 'extend',
          note: e.old_due_date
            ? `${formatDate(e.old_due_date)} → ${formatDate(e.new_due_date)}${e.reason ? ` — ${e.reason}` : ''}`
            : `новый срок ${formatDate(e.new_due_date)}${e.reason ? ` — ${e.reason}` : ''}`,
          debtId: d.id,
        })
    }
    for (const s of sales ?? [])
      events.push({ at: s.created_at, kind: 'sale', amount: s.total, saleId: s.id })
    return events.sort((a, b) => b.at.localeCompare(a.at))
  }, [debts, sales])

  if (!loading && !client) {
    return (
      <div className="stack">
        <Link to="/clients" className="back-link">
          <IconChevronLeft size={16} stroke={1.8} /> Все контрагенты
        </Link>
        <p className="error">{error ?? 'Клиент не найден'}</p>
      </div>
    )
  }

  return (
    <div className="stack">
      <Link to="/clients" className="back-link">
        <IconChevronLeft size={16} stroke={1.8} /> Все контрагенты
      </Link>

      {!client ? (
        <p className="text-muted">Загрузка…</p>
      ) : (
        <>
          <div className="client-detail-header">
            <span className="client-detail-avatar">
              <IconUser size={22} stroke={1.8} />
            </span>
            <div className="client-detail-heading">
              <div className="row" style={{ gap: 6 }}>
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
              <div className="client-detail-contacts">
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
            <div className={`client-reputation client-reputation-${reputation.level}`}>
              <ReputationIcon size={18} stroke={1.8} />
              <div className="client-reputation-text">
                <strong>{reputation.label}</strong>
                <span>{reputation.hint}</span>
              </div>
            </div>
          </div>

          <div className="client-metrics">
            <div className="client-metric">
              <span className="client-metric-icon">
                <IconWallet size={16} stroke={1.8} />
              </span>
              <div className="client-metric-body">
                <strong>{formatMoney(totalBalance)} ₽</strong>
                <span>Долг сейчас{activeDebts.length > 0 ? ` · ${activeDebts.length} шт.` : ''}</span>
              </div>
            </div>
            <div className="client-metric">
              <span className="client-metric-icon">
                <IconReceipt2 size={16} stroke={1.8} />
              </span>
              <div className="client-metric-body">
                <strong>{formatMoney(totalPurchased)} ₽</strong>
                <span>Куплено всего{sales ? ` · ${sales.length} продаж` : ''}</span>
              </div>
            </div>
            <div className="client-metric">
              <span className="client-metric-icon">
                <IconClockHour4 size={16} stroke={1.8} />
              </span>
              <div className="client-metric-body">
                <strong>{closedDebts.length}</strong>
                <span>Долгов закрыто</span>
              </div>
            </div>
          </div>

          <div className="row sale-period-tabs">
            <Button variant="secondary" active={tab === 'debts'} onClick={() => setTab('debts')}>
              Долги{debts ? ` ${debts.length}` : ''}
            </Button>
            <Button variant="secondary" active={tab === 'sales'} onClick={() => setTab('sales')}>
              Покупки{sales ? ` ${sales.length}` : ''}
            </Button>
            <Button variant="secondary" active={tab === 'history'} onClick={() => setTab('history')}>
              История
            </Button>
          </div>

          {error && <p className="error">{error}</p>}

          {tab === 'debts' &&
            (debts === null ? (
              <p className="text-muted">Загрузка…</p>
            ) : debts.length === 0 ? (
              <p className="text-muted">Долгов пока нет</p>
            ) : (
              <div className="stack" style={{ gap: 16 }}>
                <div className="debt-closed-group">
                  <div className="debt-closed-group-head">
                    Текущие долги{activeDebts.length > 0 ? ` · ${activeDebts.length}` : ''}
                  </div>
                  {activeDebts.length === 0 ? (
                    <p className="text-muted">Активных долгов нет</p>
                  ) : (
                    <div className="debt-row-list">
                      {activeDebts.map((d) => (
                        <DebtRow key={d.id} debt={d} onClick={() => openDebt(d.id)} />
                      ))}
                    </div>
                  )}
                </div>
                {closedDebts.length > 0 && (
                  <div className="debt-closed-group">
                    <div className="debt-closed-group-head">Погашенные · {closedDebts.length}</div>
                    <div className="debt-row-list">
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
              <p className="text-muted">Загрузка…</p>
            ) : sales.length === 0 ? (
              <p className="text-muted">Покупок пока нет</p>
            ) : (
              <div className="data-table">
                <div className="data-table-head" style={{ gridTemplateColumns: '1fr 1fr 1fr 20px' }}>
                  <span>Дата</span>
                  <span>Сумма</span>
                  <span>Оплата</span>
                  <span />
                </div>
                <div className="data-table-body">
                  {sales.map((s) => (
                    <div key={s.id} className="data-row" style={{ gridTemplateColumns: '1fr 1fr 1fr 20px' }}>
                      <span className="text-muted">{formatDateTime(s.created_at)}</span>
                      <span className="data-row-name">{formatMoney(s.total)} ₽</span>
                      <span className="text-muted">
                        {s.payment_method === 'cash' ? 'Наличные' : s.payment_method === 'transfer' ? 'Перевод' : 'В долг'}
                      </span>
                      <span />
                    </div>
                  ))}
                </div>
              </div>
            ))}

          {tab === 'history' &&
            (debts === null || sales === null ? (
              <p className="text-muted">Загрузка…</p>
            ) : history.length === 0 ? (
              <p className="text-muted">Событий пока нет</p>
            ) : (
              <div className="client-history-list">
                {history.map((ev, i) => {
                  const Icon =
                    ev.kind === 'sale' ? IconReceipt2 : ev.kind === 'repay' ? IconCash : IconCalendarRepeat
                  const clickable = ev.debtId != null || ev.saleId != null
                  const content = (
                    <>
                      <span className="client-history-icon">
                        <Icon size={14} stroke={1.8} />
                      </span>
                      <div className="client-history-body">
                        <span>
                          {ev.kind === 'issue' && <>Выдан долг на {formatMoney(ev.amount ?? '0')} ₽</>}
                          {ev.kind === 'repay' && (
                            <>
                              Оплата долга {formatMoney(ev.amount ?? '0')} ₽{ev.note ? ` — ${ev.note}` : ''}
                            </>
                          )}
                          {ev.kind === 'extend' && <>Продление срока — {ev.note}</>}
                          {ev.kind === 'sale' && <>Покупка на {formatMoney(ev.amount ?? '0')} ₽</>}
                        </span>
                        <span className="text-muted">{formatDate(ev.at)}</span>
                      </div>
                      {clickable && <IconChevronRight size={16} stroke={1.8} className="data-row-chevron" />}
                    </>
                  )
                  if (ev.saleId != null) {
                    return (
                      <Link
                        key={i}
                        to={`/?openSale=${ev.saleId}`}
                        className="client-history-row client-history-row-link"
                      >
                        {content}
                      </Link>
                    )
                  }
                  return (
                    <div
                      key={i}
                      className={`client-history-row${clickable ? ' client-history-row-link' : ''}`}
                      role={clickable ? 'button' : undefined}
                      tabIndex={clickable ? 0 : undefined}
                      onClick={clickable ? () => openDebt(ev.debtId!) : undefined}
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
            <p className="text-muted">Загрузка…</p>
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
                <p className="error">Долг не найден</p>
              )
            })()
          )}
        </Modal>
      )}

      {showEdit && client && (
        <Modal title="Изменить клиента" onClose={() => setShowEdit(false)}>
          <EditClientForm
            client={client}
            onDone={() => {
              setShowEdit(false)
              loadClient()
            }}
          />
        </Modal>
      )}
    </div>
  )
}

function EditClientForm({ client, onDone }: { client: Client; onDone: () => void }) {
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
      await updateClient(client.id, {
        name,
        phone,
        city,
        debt_limit: debtLimit || null,
        is_active: isActive,
      })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить клиента')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="field">
        Имя
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className="field">
        Телефон
        <PhoneInput value={phone} onChange={setPhone} />
      </label>
      <label className="field">
        Город
        <input value={city} onChange={(e) => setCity(e.target.value)} />
      </label>
      <label className="field">
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
      <label className="row" style={{ gap: 8 }}>
        <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
        Активен
      </label>
      {error && <p className="error">{error}</p>}
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
      className="debt-row"
      style={{ '--debt-accent': DEBT_STATUS_ACCENT[debt.status] } as CSSProperties}
      onClick={onClick}
    >
      <span className="debt-row-icon">
        <IconUser size={16} stroke={1.8} />
      </span>
      <div className="debt-row-main">
        <div className="debt-row-top">
          <span className="debt-row-name">{formatDate(debt.issued_at)}</span>
          <strong>{formatMoney(debt.balance)} ₽</strong>
          <span className={DEBT_STATUS_BADGE_CLASS[debt.status]}>{DEBT_STATUS_LABELS[debt.status]}</span>
        </div>
        <div className="debt-row-meta">
          <span>Остаток из {formatMoney(debt.amount)} ₽</span>
          {debt.due_date && !debt.is_closed && (
            <span className={daysOverdue(debt.due_date) > 0 ? 'text-danger' : undefined}>
              {daysOverdue(debt.due_date) > 0
                ? `Просрочен на ${daysOverdue(debt.due_date)} ${pluralDays(daysOverdue(debt.due_date))}`
                : `Срок до ${formatDate(debt.due_date)}`}
            </span>
          )}
        </div>
      </div>
      <IconChevronRight size={18} stroke={1.8} className="debt-row-chevron" />
    </button>
  )
}
