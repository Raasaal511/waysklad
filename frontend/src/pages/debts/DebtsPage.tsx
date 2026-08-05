import { useEffect, useState, type FormEvent } from 'react'
import {
  listDueDebts,
  issueDebt,
  issueSupplierDebt,
  repayDebt,
  createInstallment,
  type Debt,
} from '../../api/debts'
import { searchClients, listSuppliers, type Client, type Supplier } from '../../api/counterparties'
import { ApiError } from '../../api/client'

export function DebtsPage() {
  const [dueDebts, setDueDebts] = useState<Debt[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [due, clientList, supplierList] = await Promise.all([
        listDueDebts(),
        searchClients(),
        listSuppliers(),
      ])
      setDueDebts(due)
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
        <button type="button" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Отмена' : '+ Выдать долг'}
        </button>
      </div>

      {showForm && (
        <IssueDebtForm
          clients={clients}
          suppliers={suppliers}
          onDone={() => {
            setShowForm(false)
            load()
          }}
        />
      )}

      <h3>Должны вернуть сегодня</h3>
      {error && <p className="error">{error}</p>}
      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : dueDebts.length === 0 ? (
        <p className="text-muted">Сегодня возвратов не ожидается</p>
      ) : (
        <div className="stack">
          {dueDebts.map((d) => (
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
  const [saving, setSaving] = useState(false)
  const [showSchedule, setShowSchedule] = useState(false)

  async function handleRepay() {
    if (!amount) return
    setSaving(true)
    try {
      await repayDebt(debt.id, { amount })
      setAmount('')
      onChanged()
    } catch {
      // ошибка молча игнорируется — форма остаётся заполненной для повтора
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card card-full stack">
      <div className="row between">
        <div className="stat">
          <span>{name}</span>
          <span className="text-muted">
            Сумма {debt.amount} ₽ · остаток {debt.balance} ₽
            {debt.due_date ? ` · до ${debt.due_date}` : ''}
          </span>
        </div>
        <button type="button" className="secondary" onClick={() => setShowSchedule((v) => !v)}>
          Рассрочка
        </button>
      </div>

      <div className="row">
        <input
          type="number"
          step="0.01"
          placeholder="Сумма погашения"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          style={{ width: 140 }}
        />
        <button type="button" className="secondary" onClick={handleRepay} disabled={saving}>
          Погасить
        </button>
      </div>

      {showSchedule && (
        <InstallmentForm
          debtId={debt.id}
          balance={debt.balance}
          onDone={() => {
            setShowSchedule(false)
            onChanged()
          }}
        />
      )}
    </div>
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
          <input type="date" value={firstDate} onChange={(e) => setFirstDate(e.target.value)} />
        </label>
      </div>
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : `Разбить на ${parts} платежа по ${(Number(balance) / parts).toFixed(2)} ₽`}
      </button>
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
    setError(null)
    setSaving(true)
    try {
      if (kind === 'client') {
        if (!clientId) return
        await issueDebt({ client_id: clientId, amount, due_date: dueDate || null, note })
      } else {
        if (!supplierId) return
        await issueSupplierDebt({ supplier_id: supplierId, amount, due_date: dueDate || null, note })
      }
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось выдать долг')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form card card-full" onSubmit={handleSubmit}>
      <div className="row">
        <button
          type="button"
          className={kind === 'client' ? '' : 'secondary'}
          onClick={() => setKind('client')}
        >
          Клиенту (нам должны)
        </button>
        <button
          type="button"
          className={kind === 'supplier' ? '' : 'secondary'}
          onClick={() => setKind('supplier')}
        >
          Поставщику (мы должны)
        </button>
      </div>

      {kind === 'client' ? (
        <label className="field">
          Клиент
          <select value={clientId ?? ''} onChange={(e) => setClientId(Number(e.target.value))}>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <label className="field">
          Поставщик
          <select value={supplierId ?? ''} onChange={(e) => setSupplierId(Number(e.target.value))}>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <label className="field">
        Сумма
        <input
          type="number"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
        />
      </label>
      <label className="field">
        Обещали вернуть до
        <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
      </label>
      <label className="field">
        Заметка
        <input value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      {error && <p className="error">{error}</p>}
      <button
        type="submit"
        disabled={saving || (kind === 'client' ? !clientId : !supplierId)}
      >
        {saving ? 'Сохранение…' : 'Выдать долг'}
      </button>
    </form>
  )
}
