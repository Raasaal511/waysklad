import { useEffect, useState, type FormEvent } from 'react'
import {
  searchClients,
  createClient,
  listSuppliers,
  createSupplier,
  type Client,
  type Supplier,
} from '../../api/counterparties'
import { ApiError } from '../../api/client'

export function ClientsPage() {
  const [tab, setTab] = useState<'clients' | 'suppliers'>('clients')
  const [clients, setClients] = useState<Client[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

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

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Контрагенты</h2>
        <button type="button" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Отмена' : tab === 'clients' ? '+ Клиент' : '+ Поставщик'}
        </button>
      </div>

      <div className="row">
        <button
          type="button"
          className={tab === 'clients' ? '' : 'secondary'}
          onClick={() => setTab('clients')}
        >
          Клиенты
        </button>
        <button
          type="button"
          className={tab === 'suppliers' ? '' : 'secondary'}
          onClick={() => setTab('suppliers')}
        >
          Поставщики
        </button>
      </div>

      {showForm && tab === 'clients' && (
        <NewClientForm
          onDone={() => {
            setShowForm(false)
            load()
          }}
        />
      )}
      {showForm && tab === 'suppliers' && (
        <NewSupplierForm
          onDone={() => {
            setShowForm(false)
            load()
          }}
        />
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
                  <tr key={c.id}>
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
    <form className="form card card-full" onSubmit={handleSubmit}>
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
          type="number"
          step="0.01"
          value={debtLimit}
          onChange={(e) => setDebtLimit(e.target.value)}
        />
      </label>
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Добавить клиента'}
      </button>
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
    <form className="form card card-full" onSubmit={handleSubmit}>
      <label className="field">
        Название
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className="field">
        Контакт
        <input value={contact} onChange={(e) => setContact(e.target.value)} />
      </label>
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Добавить поставщика'}
      </button>
    </form>
  )
}
