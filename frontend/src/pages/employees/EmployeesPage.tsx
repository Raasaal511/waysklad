import { useEffect, useState, type FormEvent } from 'react'
import { listEmployees, createEmployee } from '../../entities/profile/api'
import type { Role, User } from '../../entities/auth/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { Modal } from '../../shared/ui/Modal'
import { Icon } from '../../shared/ui/icons/Icon'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'

const ROLE_LABELS: Record<Role, string> = {
  owner: 'Владелец',
  manager: 'Управляющий',
  seller: 'Продавец',
  storekeeper: 'Кладовщик',
  analyst: 'Аналитик',
}

export function EmployeesPage() {
  const { user } = useAuth()
  const [employees, setEmployees] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showEmployeeForm, setShowEmployeeForm] = useState(false)

  const canManageUsers = user?.role === 'owner' || user?.role === 'manager'

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

  if (!canManageUsers) {
    return (
      <div className="stack">
        <h2>Сотрудники</h2>
        <p className="text-muted">Доступно только владельцу и управляющему.</p>
      </div>
    )
  }

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Сотрудники</h2>
        <Button onClick={() => setShowEmployeeForm(true)}>
          <Icon name="plus" size={16} /> Сотрудник
        </Button>
      </div>

      {showEmployeeForm && (
        <Modal title="Новый сотрудник" onClose={() => setShowEmployeeForm(false)}>
          <NewEmployeeForm
            onDone={() => {
              setShowEmployeeForm(false)
              load()
            }}
          />
        </Modal>
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
    <form className="form" onSubmit={handleSubmit}>
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
        <Select
          value={role}
          onChange={(v) => setRole(v as Role)}
          options={(Object.entries(ROLE_LABELS) as [Role, string][])
            .filter(([value]) => value !== 'owner')
            .map(([value, label]) => ({ value, label }))}
        />
      </label>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Добавить сотрудника'}
      </Button>
    </form>
  )
}
