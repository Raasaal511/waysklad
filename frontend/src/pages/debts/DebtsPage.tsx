import { useEffect, useState, type FormEvent } from 'react'
import { listDueDebts, issueDebt, repayDebt, type Debt } from '../../api/debts'
import { searchClients, type Client } from '../../api/counterparties'
import { ApiError } from '../../api/client'

export function DebtsPage() {
  const [dueDebts, setDueDebts] = useState<Debt[]>([])
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [due, clientList] = await Promise.all([listDueDebts(), searchClients()])
      setDueDebts(due)
      setClients(clientList)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить долги')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const clientName = (id: number | null) => clients.find((c) => c.id === id)?.name ?? `#${id}`

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
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Клиент</th>
                <th>Сумма</th>
                <th>Остаток</th>
                <th>Срок</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {dueDebts.map((d) => (
                <DebtRow key={d.id} debt={d} clientName={clientName(d.client_id)} onRepaid={load} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function DebtRow({
  debt,
  clientName,
  onRepaid,
}: {
  debt: Debt
  clientName: string
  onRepaid: () => void
}) {
  const [amount, setAmount] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleRepay() {
    if (!amount) return
    setSaving(true)
    try {
      await repayDebt(debt.id, { amount })
      setAmount('')
      onRepaid()
    } catch {
      // ошибка молча игнорируется — форма остаётся заполненной для повтора
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr>
      <td>{clientName}</td>
      <td>{debt.amount}</td>
      <td>{debt.balance}</td>
      <td>{debt.due_date ?? '—'}</td>
      <td>
        <div className="row">
          <input
            type="number"
            step="0.01"
            placeholder="Сумма"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            style={{ width: 90 }}
          />
          <button type="button" className="secondary" onClick={handleRepay} disabled={saving}>
            Погасить
          </button>
        </div>
      </td>
    </tr>
  )
}

function IssueDebtForm({ clients, onDone }: { clients: Client[]; onDone: () => void }) {
  const [clientId, setClientId] = useState<number | null>(clients[0]?.id ?? null)
  const [amount, setAmount] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!clientId) return
    setError(null)
    setSaving(true)
    try {
      await issueDebt({ client_id: clientId, amount, due_date: dueDate || null, note })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось выдать долг')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form card card-full" onSubmit={handleSubmit}>
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
        Обещал вернуть до
        <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
      </label>
      <label className="field">
        Заметка
        <input value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={saving || !clientId}>
        {saving ? 'Сохранение…' : 'Выдать долг'}
      </button>
    </form>
  )
}
