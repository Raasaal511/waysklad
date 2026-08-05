import { useEffect, useState, type FormEvent } from 'react'
import { listEmployees, createEmployee, connectTelegram } from '../../api/profile'
import type { Role, User } from '../../api/auth'
import { ApiError } from '../../api/client'
import { useAuth } from '../../app/AuthContext'

const ROLE_LABELS: Record<Role, string> = {
  owner: 'Владелец',
  manager: 'Управляющий',
  seller: 'Продавец',
  storekeeper: 'Кладовщик',
  analyst: 'Аналитик',
}

export function ProfilePage() {
  const { user } = useAuth()
  const [employees, setEmployees] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showEmployeeForm, setShowEmployeeForm] = useState(false)

  const canManageUsers = user?.role === 'owner' || user?.role === 'manager'
  const canManageSettings = user?.role === 'owner'

  async function load() {
    if (!canManageUsers) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      setEmployees(await listEmployees())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить сотрудников')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="stack">
      <h2>Профиль магазина</h2>

      <div className="card card-full stack">
        <span className="text-muted">Вы вошли как</span>
        <strong>
          {user?.name} — {user ? ROLE_LABELS[user.role] : ''}
        </strong>
      </div>

      {canManageSettings && <TelegramSettings />}

      {canManageUsers && (
        <div className="stack">
          <div className="section-title">
            <h3>Сотрудники</h3>
            <button type="button" onClick={() => setShowEmployeeForm((v) => !v)}>
              {showEmployeeForm ? 'Отмена' : '+ Сотрудник'}
            </button>
          </div>

          {showEmployeeForm && (
            <NewEmployeeForm
              onDone={() => {
                setShowEmployeeForm(false)
                load()
              }}
            />
          )}

          {error && <p className="error">{error}</p>}
          {loading ? (
            <p className="text-muted">Загрузка…</p>
          ) : employees.length === 0 ? (
            <p className="text-muted">Кроме вас сотрудников пока нет</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Имя</th>
                    <th>Телефон</th>
                    <th>Роль</th>
                  </tr>
                </thead>
                <tbody>
                  {employees.map((e) => (
                    <tr key={e.id}>
                      <td>{e.name}</td>
                      <td>{e.phone}</td>
                      <td>{ROLE_LABELS[e.role]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function TelegramSettings() {
  const [chatId, setChatId] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [connected, setConnected] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await connectTelegram(chatId)
      setConnected(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось подключить Telegram')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form card card-full" onSubmit={handleSubmit}>
      <div>
        <h3>Telegram-сводка</h3>
        <p className="text-muted">
          Каждый вечер бот присылает: продажи, выручку, прибыль, выданные в долг суммы.
          Узнать chat_id можно у бота{' '}
          <a href="https://t.me/userinfobot" target="_blank" rel="noreferrer">
            @userinfobot
          </a>
          .
        </p>
      </div>
      <label className="field">
        Telegram chat_id
        <input value={chatId} onChange={(e) => setChatId(e.target.value)} placeholder="123456789" required />
      </label>
      {error && <p className="error">{error}</p>}
      {connected && <p className="text-muted">Подключено ✓</p>}
      <button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Подключить'}
      </button>
    </form>
  )
}

function NewEmployeeForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('seller')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await createEmployee({ name, phone, password, role })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось добавить сотрудника')
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
        <input value={phone} onChange={(e) => setPhone(e.target.value)} required />
      </label>
      <label className="field">
        Пароль
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={6}
        />
      </label>
      <label className="field">
        Роль
        <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
          {(Object.entries(ROLE_LABELS) as [Role, string][])
            .filter(([value]) => value !== 'owner')
            .map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
        </select>
      </label>
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Добавить сотрудника'}
      </button>
    </form>
  )
}
