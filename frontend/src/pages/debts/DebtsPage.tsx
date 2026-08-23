import { useEffect, useMemo, useState, type CSSProperties, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  listActiveDebts,
  listClosedDebts,
  issueDebt,
  issueSupplierDebt,
  createInstallment,
  repayDebt,
  type Debt,
} from '../../entities/debt/api'
import { searchClients, listSuppliers, type Client, type Supplier } from '../../entities/counterparty/api'
import {
  type InstallmentPeriod,
  INSTALLMENT_PERIOD_OPTIONS,
  buildInstallmentSchedule,
} from '../../entities/debt/installmentSchedule'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import {
  IconPlus,
  IconChevronRight,
  IconUser,
  IconTruck,
  IconArrowUpRight,
  IconArrowDownLeft,
  IconCalendarRepeat,
  IconSearch,
  IconClockHour4,
} from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
import { QuickNewClientForm } from '../../shared/ui/QuickNewClientForm'
import { formatMoney, normalizeDecimalInput } from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from '../../entities/debt/debtStatus'
import { daysOverdue, pluralDays } from '../../entities/debt/dueDate'

// Порядок "серьёзности" статуса — просроченные и горящие сроком долги всегда
// показываются выше спокойных, чтобы владелец сразу видел, кому звонить.
const STATUS_SEVERITY: Record<Debt['status'], number> = {
  overdue: 4,
  due_soon: 3,
  partially_paid: 2,
  active: 1,
  closed: 0,
}

// Цвет левой полоски карточки долга — тот же смысл, что у бейджа статуса,
// но как акцент, по которому можно опознать "горящий" долг не читая текст.
const DEBT_STATUS_ACCENT: Record<Debt['status'], string> = {
  active: 'var(--border)',
  due_soon: 'var(--warning)',
  overdue: 'var(--danger)',
  partially_paid: 'var(--warning)',
  closed: 'var(--accent)',
}

const STATUS_FILTERS: { value: Debt['status'] | 'all'; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'overdue', label: 'Просрочен' },
  { value: 'due_soon', label: 'Скоро срок' },
  { value: 'partially_paid', label: 'Погашен частично' },
  { value: 'active', label: 'Активен' },
]

// Дата, которой считаем долг закрытым — последняя оплата (если она была);
// нужна только для группировки погашённых долгов по месяцу на отдельной
// вкладке, в данных нет отдельного closed_at.
function closedOn(debt: Debt): string {
  if (debt.repayments.length === 0) return debt.issued_at
  return debt.repayments.reduce((latest, r) => (r.on > latest ? r.on : latest), debt.repayments[0].on)
}

function monthLabel(dateStr: string): string {
  const label = new Date(dateStr).toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
  return label.charAt(0).toUpperCase() + label.slice(1)
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('ru-RU')
}

const DUE_DATE_PRESETS: { label: string; days: number }[] = [
  { label: 'Неделя', days: 7 },
  { label: '2 мес.', days: 60 },
  { label: '3 мес.', days: 90 },
  { label: '4 мес.', days: 120 },
  { label: 'Полгода', days: 182 },
  { label: 'Год', days: 365 },
]

function addDays(days: number) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

function DueDatePresets({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="debt-due-date-presets">
      {DUE_DATE_PRESETS.map((p) => {
        const presetValue = addDays(p.days)
        return (
          <button
            key={p.label}
            type="button"
            className={`debt-due-date-preset${value === presetValue ? ' debt-due-date-preset-active' : ''}`}
            onClick={() => onChange(presetValue)}
          >
            {p.label}
          </button>
        )
      })}
    </div>
  )
}

interface UpcomingPayment {
  debtId: number
  dueDate: string
  amount: string
  name: string
}

// Ближайшие неоплаченные платежи графиков рассрочки по всем активным долгам —
// та же эвристика "оплачено покрывает платежи по порядку", что и в карточке
// долга: связи Repayment→InstallmentPayment в данных нет.
function upcomingPayments(debts: Debt[], counterpartyName: (d: Debt) => string): UpcomingPayment[] {
  const result: UpcomingPayment[] = []
  for (const debt of debts) {
    if (debt.schedule.length === 0) continue
    let paidSoFar = debt.repayments.reduce((sum, r) => sum + Number(r.amount), 0)
    for (const s of debt.schedule) {
      const amount = Number(s.amount)
      if (paidSoFar >= amount - 0.01) {
        paidSoFar -= amount
        continue
      }
      result.push({ debtId: debt.id, dueDate: s.due_date, amount: s.amount, name: counterpartyName(debt) })
    }
  }
  return result.sort((a, b) => a.dueDate.localeCompare(b.dueDate))
}

export function DebtsPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const highlightId = searchParams.get('highlight')
  const [debts, setDebts] = useState<Debt[]>([])
  const [closedDebts, setClosedDebts] = useState<Debt[] | null>(null)
  const [loadingClosed, setLoadingClosed] = useState(false)
  const [clients, setClients] = useState<Client[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [showUpcoming, setShowUpcoming] = useState(false)
  const [view, setView] = useState<'active' | 'closed'>('active')
  const [direction, setDirection] = useState<'clients' | 'suppliers'>('clients')
  const [statusFilter, setStatusFilter] = useState<Debt['status'] | 'all'>('all')
  const [query, setQuery] = useState('')

  async function load() {
    setLoading(true)
    try {
      const [activeDebts, clientList, supplierList] = await Promise.all([
        listActiveDebts(),
        searchClients(),
        listSuppliers(),
      ])
      setDebts(activeDebts)
      setClients(clientList)
      setSuppliers(supplierList)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить долги')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  // Погашенные долги не нужны по умолчанию — грузим только когда владелец
  // действительно открыл вкладку "Погашенные".
  useEffect(() => {
    if (view !== 'closed' || closedDebts !== null) return
    setLoadingClosed(true)
    listClosedDebts()
      .then(setClosedDebts)
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Не удалось загрузить погашенные долги'))
      .finally(() => setLoadingClosed(false))
  }, [view, closedDebts])

  const counterpartyName = (debt: Debt) =>
    debt.client_id
      ? clients.find((c) => c.id === debt.client_id)?.name ?? `Клиент #${debt.client_id}`
      : suppliers.find((s) => s.id === debt.supplier_id)?.name ?? `Поставщик #${debt.supplier_id}`

  const clientDebts = useMemo(() => debts.filter((d) => d.client_id != null), [debts])
  const supplierDebts = useMemo(() => debts.filter((d) => d.supplier_id != null), [debts])
  const totalOwedToUs = clientDebts.reduce((sum, d) => sum + Number(d.balance), 0)
  const totalWeOwe = supplierDebts.reduce((sum, d) => sum + Number(d.balance), 0)

  const visibleDebts = useMemo(() => {
    const byDirection = debts.filter((d) => (direction === 'clients' ? d.client_id != null : d.supplier_id != null))
    const byStatus = statusFilter === 'all' ? byDirection : byDirection.filter((d) => d.status === statusFilter)
    const trimmedQuery = query.trim().toLowerCase()
    const filtered = trimmedQuery
      ? byStatus.filter((d) => counterpartyName(d).toLowerCase().includes(trimmedQuery))
      : byStatus
    return [...filtered].sort((a, b) => {
      const bySeverity = STATUS_SEVERITY[b.status] - STATUS_SEVERITY[a.status]
      if (bySeverity !== 0) return bySeverity
      return (a.due_date ?? '9999').localeCompare(b.due_date ?? '9999')
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [direction, statusFilter, debts, query, clients, suppliers])

  // Погашенные — отдельной вкладкой, сгруппированы по месяцу закрытия (месяц
  // последней оплаты), последние группы сверху.
  const closedGroups = useMemo(() => {
    const trimmedQuery = query.trim().toLowerCase()
    const source = closedDebts ?? []
    const filtered = trimmedQuery
      ? source.filter((d) => counterpartyName(d).toLowerCase().includes(trimmedQuery))
      : source
    const sorted = [...filtered].sort((a, b) => closedOn(b).localeCompare(closedOn(a)))
    const groups: { label: string; items: Debt[] }[] = []
    for (const d of sorted) {
      const label = monthLabel(closedOn(d))
      const group = groups.at(-1)?.label === label ? groups.at(-1)! : { label, items: [] }
      if (groups.at(-1) !== group) groups.push(group)
      group.items.push(d)
    }
    return groups
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [closedDebts, query, clients, suppliers])

  const upcoming = useMemo(
    () => upcomingPayments(debts, counterpartyName),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [debts, clients, suppliers],
  )

  // Переход по ссылке "?highlight=id" (из уведомления, из продажи) — сразу
  // открываем карточку конкретного долга.
  useEffect(() => {
    if (loading || !highlightId) return
    const debt = debts.find((d) => String(d.id) === highlightId)
    if (!debt) return
    navigate(`/debts/${debt.id}`, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, highlightId, debts])

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Долги</h2>
        <div className="row" style={{ gap: 8 }}>
          {upcoming.length > 0 && (
            <Button variant="secondary" onClick={() => setShowUpcoming(true)}>
              <IconClockHour4 size={16} stroke={1.8} /> Выплаты
              <span className="count-badge">{upcoming.length}</span>
            </Button>
          )}
          <Button onClick={() => setShowForm(true)}>
            <IconPlus size={16} stroke={1.8} /> Выдать долг
          </Button>
        </div>
      </div>

      {showForm && (
        <Modal title="Выдать долг" onClose={() => setShowForm(false)}>
          <IssueDebtForm
            clients={clients}
            onClientCreated={(client) => setClients((prev) => [...prev, client])}
            suppliers={suppliers}
            onDone={() => {
              setShowForm(false)
              load()
            }}
          />
        </Modal>
      )}

      {error && <p className="error">{error}</p>}

      {showUpcoming && (
        <Modal title="Ближайшие выплаты" onClose={() => setShowUpcoming(false)}>
          <div className="debt-upcoming-list debt-upcoming-list-modal">
            {upcoming.map((p, i) => {
              const overdue = daysOverdue(p.dueDate) > 0
              return (
                <button
                  key={i}
                  type="button"
                  className="debt-upcoming-row"
                  onClick={() => {
                    setShowUpcoming(false)
                    navigate(`/debts/${p.debtId}`)
                  }}
                >
                  <span className={`debt-upcoming-date${overdue ? ' text-danger' : ''}`}>
                    {formatDate(p.dueDate)}
                  </span>
                  <span className="debt-upcoming-name">{p.name}</span>
                  {overdue && (
                    <span className="text-danger debt-upcoming-overdue">
                      просрочен на {daysOverdue(p.dueDate)} {pluralDays(daysOverdue(p.dueDate))}
                    </span>
                  )}
                  <strong className="debt-upcoming-amount">{formatMoney(p.amount)} ₽</strong>
                  <IconChevronRight size={16} stroke={1.8} className="data-row-chevron" />
                </button>
              )
            })}
          </div>
        </Modal>
      )}

      <div className="sale-period-tabs">
        <Button variant="secondary" active={view === 'active'} onClick={() => setView('active')}>
          Активные
        </Button>
        <Button variant="secondary" active={view === 'closed'} onClick={() => setView('closed')}>
          Погашенные
        </Button>
      </div>

      {!loading && view === 'active' && (
        <div className="debt-tabs">
          <button
            type="button"
            className={`debt-tab debt-tab-owed-to-us${direction === 'clients' ? ' debt-tab-active' : ''}`}
            onClick={() => setDirection('clients')}
          >
            <span className="debt-tab-label">
              <IconArrowDownLeft size={14} stroke={2} /> Нам должны клиенты
            </span>
            <strong>{formatMoney(String(totalOwedToUs))} ₽</strong>
            {clientDebts.length > 0 && <span className="count-badge">{clientDebts.length}</span>}
          </button>
          <button
            type="button"
            className={`debt-tab debt-tab-we-owe${direction === 'suppliers' ? ' debt-tab-active' : ''}`}
            onClick={() => setDirection('suppliers')}
          >
            <span className="debt-tab-label">
              <IconArrowUpRight size={14} stroke={2} /> Мы должны поставщикам
            </span>
            <strong>{formatMoney(String(totalWeOwe))} ₽</strong>
            {supplierDebts.length > 0 && <span className="count-badge">{supplierDebts.length}</span>}
          </button>
        </div>
      )}

      {!loading && (
        <div className="sale-search-panel">
          <div className="sale-search-row">
            <IconSearch size={16} stroke={1.8} className="sale-search-icon" />
            <input
              className="sale-search-input"
              placeholder="Поиск по клиенту или поставщику…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>
      )}

      {!loading && view === 'active' && (
        <div className="debt-status-filters">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              className={`debt-status-filter${statusFilter === f.value ? ' debt-status-filter-active' : ''}`}
              onClick={() => setStatusFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}

      {view === 'active' ? (
        loading ? (
          <p className="text-muted">Загрузка…</p>
        ) : visibleDebts.length === 0 ? (
          <p className="text-muted">
            {query.trim()
              ? 'Ничего не найдено'
              : statusFilter === 'all'
                ? 'Долгов нет'
                : 'Долгов с таким статусом нет'}
          </p>
        ) : (
          <div className="debt-row-list">
            {visibleDebts.map((d) => (
              <DebtRow key={d.id} debt={d} name={counterpartyName(d)} onOpen={() => navigate(`/debts/${d.id}`)} />
            ))}
          </div>
        )
      ) : loadingClosed ? (
        <p className="text-muted">Загрузка…</p>
      ) : closedGroups.length === 0 ? (
        <p className="text-muted">{query.trim() ? 'Ничего не найдено' : 'Погашенных долгов нет'}</p>
      ) : (
        <div className="stack">
          {closedGroups.map((group) => (
            <div key={group.label} className="debt-closed-group">
              <div className="debt-closed-group-head">
                <span>{group.label}</span>
                <span className="text-muted">{group.items.length}</span>
              </div>
              <div className="debt-row-list">
                {group.items.map((d) => (
                  <DebtRow key={d.id} debt={d} name={counterpartyName(d)} onOpen={() => navigate(`/debts/${d.id}`)} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function DebtRow({ debt, name, onOpen }: { debt: Debt; name: string; onOpen: () => void }) {
  const Icon = debt.client_id != null ? IconUser : IconTruck

  return (
    <div
      className="debt-row"
      style={{ '--debt-accent': DEBT_STATUS_ACCENT[debt.status] } as CSSProperties}
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onOpen()
      }}
    >
      <span className="debt-row-icon">
        <Icon size={16} stroke={1.8} />
      </span>
      <div className="debt-row-main">
        <div className="debt-row-top">
          <span className="debt-row-name">{name}</span>
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
          {debt.schedule.length > 0 && (
            <span className="debt-row-installment">
              <IconCalendarRepeat size={13} stroke={1.8} /> Рассрочка на {debt.schedule.length}
            </span>
          )}
        </div>
      </div>
      <IconChevronRight size={18} stroke={1.8} className="debt-row-chevron" />
    </div>
  )
}

function IssueDebtForm({
  clients,
  onClientCreated,
  suppliers,
  onDone,
}: {
  clients: Client[]
  onClientCreated: (client: Client) => void
  suppliers: Supplier[]
  onDone: () => void
}) {
  const [kind, setKind] = useState<'client' | 'supplier'>('client')
  const [clientId, setClientId] = useState<number | null>(clients[0]?.id ?? null)
  const [showNewClientForm, setShowNewClientForm] = useState(false)
  const [supplierId, setSupplierId] = useState<number | null>(suppliers[0]?.id ?? null)
  const [amount, setAmount] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [note, setNote] = useState('')
  const [withInstallment, setWithInstallment] = useState(false)
  const [downPayment, setDownPayment] = useState('')
  const [parts, setParts] = useState(3)
  const [period, setPeriod] = useState<InstallmentPeriod>('month')
  const [firstPaymentDate, setFirstPaymentDate] = useState(new Date().toISOString().slice(0, 10))
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const downPaymentNum = Number(downPayment || '0')
  const downPaymentInvalid = downPaymentNum < 0 || (amount !== '' && downPaymentNum >= Number(amount))
  const remainingAfterDownPayment = Math.max(Number(amount || '0') - downPaymentNum, 0).toFixed(2)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!dueDate) {
      setError('Укажите срок «Долг до»')
      return
    }
    if (withInstallment && !firstPaymentDate) {
      setError('Укажите дату первого платежа рассрочки')
      return
    }
    if (withInstallment && downPaymentInvalid) {
      setError('Первый взнос должен быть меньше суммы долга')
      return
    }
    setError(null)
    setSaving(true)
    try {
      const debt =
        kind === 'client'
          ? clientId && (await issueDebt({ client_id: clientId, amount, due_date: dueDate, note }))
          : supplierId && (await issueSupplierDebt({ supplier_id: supplierId, amount, due_date: dueDate, note }))
      if (!debt) return
      if (withInstallment) {
        if (downPaymentNum > 0) {
          await repayDebt(debt.id, { amount: downPayment, paid_on: firstPaymentDate, note: 'Первый взнос' })
        }
        await createInstallment(
          debt.id,
          buildInstallmentSchedule(remainingAfterDownPayment, parts, firstPaymentDate, period),
        )
      }
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось выдать долг')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <div className="row">
        <Button variant={kind === 'client' ? 'primary' : 'secondary'} onClick={() => setKind('client')}>
          Клиенту (нам должны)
        </Button>
        <Button variant={kind === 'supplier' ? 'primary' : 'secondary'} onClick={() => setKind('supplier')}>
          Поставщику (мы должны)
        </Button>
      </div>

      {kind === 'client' ? (
        <label className="field">
          Клиент
          <div className="sale-client-row">
            <Select
              value={clientId != null ? String(clientId) : ''}
              onChange={(v) => setClientId(Number(v))}
              options={clients.map((c) => ({ value: String(c.id), label: c.name }))}
            />
            <QuickNewClientForm
              open={showNewClientForm}
              onOpenChange={setShowNewClientForm}
              trigger={
                <Button type="button" variant="secondary" onClick={() => setShowNewClientForm(true)}>
                  <IconPlus size={16} stroke={1.8} /> Клиент
                </Button>
              }
              onCreated={(client) => {
                onClientCreated(client)
                setClientId(client.id)
                setShowNewClientForm(false)
              }}
            />
          </div>
        </label>
      ) : (
        <label className="field">
          Поставщик
          <Select
            value={supplierId != null ? String(supplierId) : ''}
            onChange={(v) => setSupplierId(Number(v))}
            options={suppliers.map((s) => ({ value: String(s.id), label: s.name }))}
          />
        </label>
      )}

      <label className="field">
        Сумма
        <input
          type="text"
          inputMode="decimal"
          value={amount}
          onChange={(e) => {
            const normalized = normalizeDecimalInput(e.target.value)
            if (normalized !== null) setAmount(normalized)
          }}
          required
        />
      </label>
      <label className="field">
        Долг до
        <DateInput
          value={dueDate}
          min={new Date().toISOString().slice(0, 10)}
          onChange={setDueDate}
          required
        />
      </label>
      <DueDatePresets value={dueDate} onChange={setDueDate} />
      <label className="field">
        Заметка
        <input value={note} onChange={(e) => setNote(e.target.value)} />
      </label>

      <label className="sale-checkbox">
        <input
          type="checkbox"
          checked={withInstallment}
          onChange={(e) => setWithInstallment(e.target.checked)}
        />
        С рассрочкой
      </label>

      {withInstallment && (
        <div className="stack" style={{ gap: 14 }}>
          <label className="field">
            Первый взнос (необязательно)
            <input
              type="text"
              inputMode="decimal"
              placeholder="0"
              value={downPayment}
              onChange={(e) => {
                const normalized = normalizeDecimalInput(e.target.value)
                if (normalized !== null) setDownPayment(normalized)
              }}
            />
          </label>
          {downPaymentNum > 0 && (
            <p className={downPaymentInvalid ? 'error' : 'text-muted'}>
              {downPaymentInvalid
                ? 'Первый взнос должен быть меньше суммы долга'
                : `В рассрочку пойдёт ${formatMoney(remainingAfterDownPayment)} ₽`}
            </p>
          )}
          <div className="row">
            <label className="field" style={{ flex: 1 }}>
              Платежей
              <input
                type="number"
                min={2}
                max={12}
                value={parts}
                onChange={(e) => setParts(Number(e.target.value))}
              />
            </label>
            <label className="field" style={{ flex: 1 }}>
              Периодичность
              <Select
                value={period}
                onChange={(v) => setPeriod(v as InstallmentPeriod)}
                options={INSTALLMENT_PERIOD_OPTIONS}
              />
            </label>
          </div>
          <label className="field">
            {downPaymentNum > 0 ? 'Дата первого взноса и старт графика' : 'Первый платёж'}
            <DateInput
              value={firstPaymentDate}
              min={new Date().toISOString().slice(0, 10)}
              onChange={setFirstPaymentDate}
            />
          </label>
        </div>
      )}

      {error && <p className="error">{error}</p>}
      <Button
        type="submit"
        disabled={
          saving ||
          (kind === 'client' ? !clientId : !supplierId) ||
          (withInstallment && downPaymentInvalid)
        }
      >
        {saving ? 'Сохранение…' : 'Выдать долг'}
      </Button>
    </form>
  )
}
