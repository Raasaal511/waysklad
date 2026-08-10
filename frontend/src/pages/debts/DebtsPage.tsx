import { useEffect, useState, type FormEvent } from 'react'
import {
  listActiveDebts,
  issueDebt,
  issueSupplierDebt,
  repayDebt,
  extendDebt,
  createInstallment,
  getDebtHistory,
  type Debt,
  type DebtHistoryEntry,
} from '../../entities/debt/api'
import { searchClients, listSuppliers, type Client, type Supplier } from '../../entities/counterparty/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { Icon } from '../../shared/ui/icons/Icon'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
import { formatMoney, normalizeDecimalInput } from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from '../../entities/debt/debtStatus'

const DEBT_HISTORY_ACTION_LABELS: Record<string, string> = {
  'debt.issue': 'Долг выдан',
  'debt.issue_supplier': 'Долг выдан поставщиком',
  'debt.repay': 'Внесена оплата',
  'debt.installment': 'Составлен график рассрочки',
  'debt.extend': 'Срок продлён',
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('ru-RU')
}

export function DebtsPage() {
  const [debts, setDebts] = useState<Debt[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

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

  const counterpartyName = (debt: Debt) =>
    debt.client_id
      ? clients.find((c) => c.id === debt.client_id)?.name ?? `Клиент #${debt.client_id}`
      : suppliers.find((s) => s.id === debt.supplier_id)?.name ?? `Поставщик #${debt.supplier_id}`

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Долги</h2>
        <Button onClick={() => setShowForm(true)}>
          <Icon name="plus" size={16} /> Выдать долг
        </Button>
      </div>

      {showForm && (
        <Modal title="Выдать долг" onClose={() => setShowForm(false)}>
          <IssueDebtForm
            clients={clients}
            suppliers={suppliers}
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
      ) : debts.length === 0 ? (
        <p className="text-muted">Активных долгов нет</p>
      ) : (
        <div className="stack">
          {debts.map((d) => (
            <DebtCard key={d.id} debt={d} name={counterpartyName(d)} onChanged={load} />
          ))}
        </div>
      )}
    </div>
  )
}

function DebtCard({
  debt,
  name,
  onChanged,
}: {
  debt: Debt
  name: string
  onChanged: () => void
}) {
  const [amount, setAmount] = useState('')
  const [paidOn, setPaidOn] = useState(new Date().toISOString().slice(0, 10))
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [repayError, setRepayError] = useState<string | null>(null)
  const [showSchedule, setShowSchedule] = useState(false)
  const [showExtend, setShowExtend] = useState(false)
  const [history, setHistory] = useState<DebtHistoryEntry[] | null>(null)
  const [loadingHistory, setLoadingHistory] = useState(false)

  async function handleRepay() {
    if (!amount) return
    setSaving(true)
    setRepayError(null)
    try {
      await repayDebt(debt.id, { amount, paid_on: paidOn, note })
      setAmount('')
      setNote('')
      onChanged()
    } catch (err) {
      setRepayError(err instanceof ApiError ? err.message : 'Не удалось внести оплату')
    } finally {
      setSaving(false)
    }
  }

  async function loadHistory() {
    setLoadingHistory(true)
    try {
      setHistory(await getDebtHistory(debt.id))
    } catch {
      setHistory([])
    } finally {
      setLoadingHistory(false)
    }
  }

  return (
    <div className="card card-full stack">
      <div className="row between wrap" style={{ gap: 8 }}>
        <div className="stat">
          <span>{name}</span>
          <span className="text-muted">
            Сумма {formatMoney(debt.amount)} ₽ · остаток {formatMoney(debt.balance)} ₽
            {debt.due_date ? ` · до ${formatDate(debt.due_date)}` : ''}
          </span>
        </div>
        <div className="row wrap" style={{ gap: 8 }}>
          <span className={DEBT_STATUS_BADGE_CLASS[debt.status]}>
            {DEBT_STATUS_LABELS[debt.status]}
          </span>
          <Button variant="secondary" onClick={() => setShowExtend(true)}>
            Продлить
          </Button>
          <Button variant="secondary" onClick={() => setShowSchedule(true)}>
            Рассрочка
          </Button>
        </div>
      </div>

      <div className="row wrap" style={{ gap: 8 }}>
        <input
          type="text"
          inputMode="decimal"
          placeholder="Сумма"
          value={amount}
          onChange={(e) => {
            const normalized = normalizeDecimalInput(e.target.value)
            if (normalized !== null) setAmount(normalized)
          }}
          style={{ width: 100 }}
        />
        <DateInput value={paidOn} onChange={setPaidOn} className="debt-repay-date" />
        <input
          placeholder="Комментарий"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          style={{ flex: 1, minWidth: 140 }}
        />
        <Button variant="secondary" onClick={handleRepay} disabled={saving}>
          {saving ? 'Сохранение…' : 'Внести оплату'}
        </Button>
      </div>
      {repayError && <p className="error">{repayError}</p>}

      <div className="debt-history">
        {history === null ? (
          <Button variant="secondary" onClick={loadHistory} disabled={loadingHistory}>
            {loadingHistory ? 'Загрузка…' : 'История платежей и изменений'}
          </Button>
        ) : history.length === 0 ? (
          <p className="text-muted">История пуста</p>
        ) : (
          <div className="stack" style={{ gap: 4 }}>
            {history.map((entry) => (
              <div key={entry.id} className="debt-history-item">
                <span>{DEBT_HISTORY_ACTION_LABELS[entry.action] ?? entry.action}</span>
                <span className="text-muted">{formatDate(entry.created_at)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {showSchedule && (
        <Modal title={`Рассрочка · ${name}`} onClose={() => setShowSchedule(false)}>
          <InstallmentForm
            debtId={debt.id}
            balance={debt.balance}
            onDone={() => {
              setShowSchedule(false)
              onChanged()
            }}
          />
        </Modal>
      )}

      {showExtend && (
        <Modal title={`Продлить долг · ${name}`} onClose={() => setShowExtend(false)}>
          <ExtendDebtForm
            debtId={debt.id}
            currentDueDate={debt.due_date}
            onDone={() => {
              setShowExtend(false)
              onChanged()
            }}
          />
        </Modal>
      )}
    </div>
  )
}

function ExtendDebtForm({
  debtId,
  currentDueDate,
  onDone,
}: {
  debtId: number
  currentDueDate: string | null
  onDone: () => void
}) {
  const [newDueDate, setNewDueDate] = useState(currentDueDate ?? '')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!newDueDate) return
    setError(null)
    setSaving(true)
    try {
      await extendDebt(debtId, { new_due_date: newDueDate, reason })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось продлить долг')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      {currentDueDate && (
        <p className="text-muted">Текущий срок: {formatDate(currentDueDate)}</p>
      )}
      <label className="field">
        Новый срок «Долг до»
        <DateInput value={newDueDate} onChange={setNewDueDate} required />
      </label>
      <label className="field">
        Причина
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Например: попросил ещё неделю"
        />
      </label>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Продлить'}
      </Button>
    </form>
  )
}

function InstallmentForm({
  debtId,
  balance,
  onDone,
}: {
  debtId: number
  balance: string
  onDone: () => void
}) {
  const [parts, setParts] = useState(3)
  const [firstDate, setFirstDate] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!firstDate) return
    setError(null)
    setSaving(true)
    try {
      const total = Number(balance)
      const perPart = (total / parts).toFixed(2)
      const schedule = Array.from({ length: parts }, (_, i) => {
        const date = new Date(firstDate)
        date.setMonth(date.getMonth() + i)
        return { due_date: date.toISOString().slice(0, 10), amount: perPart }
      })
      await createInstallment(debtId, schedule)
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось составить график')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
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
          Первый платёж
          <DateInput value={firstDate} onChange={setFirstDate} />
        </label>
      </div>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : `Разбить на ${parts} платежа по ${(Number(balance) / parts).toFixed(2)} ₽`}
      </Button>
    </form>
  )
}

function IssueDebtForm({
  clients,
  suppliers,
  onDone,
}: {
  clients: Client[]
  suppliers: Supplier[]
  onDone: () => void
}) {
  const [kind, setKind] = useState<'client' | 'supplier'>('client')
  const [clientId, setClientId] = useState<number | null>(clients[0]?.id ?? null)
  const [supplierId, setSupplierId] = useState<number | null>(suppliers[0]?.id ?? null)
  const [amount, setAmount] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!dueDate) {
      setError('Укажите срок «Долг до»')
      return
    }
    setError(null)
    setSaving(true)
    try {
      if (kind === 'client') {
        if (!clientId) return
        await issueDebt({ client_id: clientId, amount, due_date: dueDate, note })
      } else {
        if (!supplierId) return
        await issueSupplierDebt({ supplier_id: supplierId, amount, due_date: dueDate, note })
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
          <Select
            value={clientId != null ? String(clientId) : ''}
            onChange={(v) => setClientId(Number(v))}
            options={clients.map((c) => ({ value: String(c.id), label: c.name }))}
          />
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
      <label className="field">
        Заметка
        <input value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving || (kind === 'client' ? !clientId : !supplierId)}>
        {saving ? 'Сохранение…' : 'Выдать долг'}
      </Button>
    </form>
  )
}
