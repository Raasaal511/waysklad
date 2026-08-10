import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  searchClients,
  createClient,
  listSuppliers,
  createSupplier,
  type Client,
  type Supplier,
} from '../../entities/counterparty/api'
import { listClientDebts, type Debt } from '../../entities/debt/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { Icon } from '../../shared/ui/icons/Icon'
import { Button } from '../../shared/ui/Button'
import { formatMoney, normalizeDecimalInput } from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from '../../entities/debt/debtStatus'

export function ClientsPage() {
  const [searchParams] = useSearchParams()
  const highlightId = searchParams.get('highlight')
  const [tab, setTab] = useState<'clients' | 'suppliers'>('clients')
  const [clients, setClients] = useState<Client[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [selectedClient, setSelectedClient] = useState<Client | null>(null)
  const highlightRef = useRef<HTMLTableRowElement>(null)

  async function load() {
    setLoading(true)
    try {
      const [c, s] = await Promise.all([searchClients(), listSuppliers()])
      setClients(c)
      setSuppliers(s)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить контрагентов')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (!loading && highlightId) {
      highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [loading, highlightId])

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Контрагенты</h2>
        <Button onClick={() => setShowForm(true)}>
          <Icon name="plus" size={16} /> {tab === 'clients' ? 'Клиент' : 'Поставщик'}
        </Button>
      </div>

      <div className="row">
        <Button variant={tab === 'clients' ? 'primary' : 'secondary'} onClick={() => setTab('clients')}>
          Клиенты
        </Button>
        <Button variant={tab === 'suppliers' ? 'primary' : 'secondary'} onClick={() => setTab('suppliers')}>
          Поставщики
        </Button>
      </div>

      {showForm && tab === 'clients' && (
        <Modal title="Новый клиент" onClose={() => setShowForm(false)}>
          <NewClientForm
            onDone={() => {
              setShowForm(false)
              load()
            }}
          />
        </Modal>
      )}
      {showForm && tab === 'suppliers' && (
        <Modal title="Новый поставщик" onClose={() => setShowForm(false)}>
          <NewSupplierForm
            onDone={() => {
              setShowForm(false)
              load()
            }}
          />
        </Modal>
      )}

      {selectedClient && (
        <Modal title={selectedClient.name} onClose={() => setSelectedClient(null)}>
          <ClientDebtsSummary client={selectedClient} />
        </Modal>
      )}

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : tab === 'clients' ? (
        clients.length === 0 ? (
          <p className="text-muted">Клиентов пока нет</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Имя</th>
                  <th>Телефон</th>
                  <th>Город</th>
                  <th>Лимит долга</th>
                </tr>
              </thead>
              <tbody>
                {clients.map((c) => (
                  <tr
                    key={c.id}
                    ref={String(c.id) === highlightId ? highlightRef : undefined}
                    className={`client-row${String(c.id) === highlightId ? ' row-highlight' : ''}`}
                    onClick={() => setSelectedClient(c)}
                  >
                    <td>{c.name}</td>
                    <td>{c.phone || '—'}</td>
                    <td>{c.city || '—'}</td>
                    <td>{c.debt_limit ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : suppliers.length === 0 ? (
        <p className="text-muted">Поставщиков пока нет</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Название</th>
                <th>Контакт</th>
              </tr>
            </thead>
            <tbody>
              {suppliers.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.contact || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function ClientDebtsSummary({ client }: { client: Client }) {
  const [debts, setDebts] = useState<Debt[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listClientDebts(client.id)
      .then((summary) => setDebts(summary.debts))
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Не удалось загрузить долги'))
  }, [client.id])

  const active = debts?.filter((d) => !d.is_closed) ?? []
  const closed = debts?.filter((d) => d.is_closed) ?? []
  const totalBalance = active.reduce((sum, d) => sum + Number(d.balance), 0)

  return (
    <div className="stack">
      <div className="row wrap" style={{ gap: 12 }}>
        {client.phone && <span className="text-muted">{client.phone}</span>}
        {client.city && <span className="text-muted">{client.city}</span>}
        {client.debt_limit && <span className="text-muted">Лимит долга: {formatMoney(client.debt_limit)} ₽</span>}
      </div>

      <h3>Долги</h3>
      {error && <p className="error">{error}</p>}
      {debts === null ? (
        <p className="text-muted">Загрузка…</p>
      ) : debts.length === 0 ? (
        <p className="text-muted">Долгов нет</p>
      ) : (
        <div className="stack" style={{ gap: 8 }}>
          {active.length > 0 && (
            <p className="text-muted">Активных долгов на {formatMoney(totalBalance)} ₽</p>
          )}
          {[...active, ...closed].map((d) => (
            <div key={d.id} className="client-debt-item">
              <span className={DEBT_STATUS_BADGE_CLASS[d.status]}>{DEBT_STATUS_LABELS[d.status]}</span>
              <span>{formatMoney(d.balance)} ₽ из {formatMoney(d.amount)} ₽</span>
              {d.due_date && (
                <span className="text-muted">до {new Date(d.due_date).toLocaleDateString('ru-RU')}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function NewClientForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [city, setCity] = useState('')
  const [debtLimit, setDebtLimit] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await createClient({ name, phone, city, debt_limit: debtLimit || null })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось добавить клиента')
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
        <input value={phone} onChange={(e) => setPhone(e.target.value)} />
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
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Добавить клиента'}
      </Button>
    </form>
  )
}

function NewSupplierForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState('')
  const [contact, setContact] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await createSupplier({ name, contact })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось добавить поставщика')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="field">
        Название
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className="field">
        Контакт
        <input value={contact} onChange={(e) => setContact(e.target.value)} />
      </label>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Добавить поставщика'}
      </Button>
    </form>
  )
}
