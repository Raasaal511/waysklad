import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { listEmployees, createEmployee, updateEmployee } from '../../entities/profile/api'
import type { Role, User } from '../../entities/auth/api'
import { listWarehouses, type Warehouse } from '../../entities/inventory/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { Modal } from '../../shared/ui/Modal'
import { IconPlus, IconChevronRight } from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { PhoneInput } from '../../shared/ui/PhoneInput'

const ROLE_LABELS: Record<Role, string> = {
  owner: 'Владелец',
  manager: 'Управляющий',
  seller: 'Продавец',
  storekeeper: 'Кладовщик',
  analyst: 'Аналитик',
}

// роли, которые можно назначить из формы сотрудника; аналитика больше не заводим —
// роль остаётся в системе только для уже существующих пользователей
const ASSIGNABLE_ROLES: Role[] = ['manager', 'seller', 'storekeeper']

// роли, для которых нужна привязка к складу (минимум один)
const WAREHOUSE_SCOPED_ROLES: Role[] = ['manager', 'seller', 'storekeeper']

const EMPLOYEE_COLUMNS = '1.2fr 1fr 1fr 1.4fr 20px'

export function EmployeesPage() {
  const { user } = useAuth()
  const [employees, setEmployees] = useState<User[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showEmployeeForm, setShowEmployeeForm] = useState(false)
  const [editingEmployee, setEditingEmployee] = useState<User | null>(null)

  const canManageUsers = user?.role === 'owner' || user?.role === 'manager'

  async function load() {
    if (!canManageUsers) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const [employeeList, warehouseList] = await Promise.all([listEmployees(), listWarehouses()])
      setEmployees(employeeList)
      setWarehouses(warehouseList)
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

  const warehouseNameById = new Map(warehouses.map((w) => [w.id, w.name]))

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Сотрудники</h2>
        <Button onClick={() => setShowEmployeeForm(true)}>
          <IconPlus size={16} stroke={1.8} /> Сотрудник
        </Button>
      </div>

      {showEmployeeForm && (
        <Modal title="Новый сотрудник" onClose={() => setShowEmployeeForm(false)}>
          <EmployeeForm
            warehouses={warehouses}
            onDone={() => {
              setShowEmployeeForm(false)
              load()
            }}
          />
        </Modal>
      )}

      {editingEmployee && (
        <Modal title="Сотрудник" onClose={() => setEditingEmployee(null)}>
          <EmployeeForm
            warehouses={warehouses}
            employee={editingEmployee}
            onDone={() => {
              setEditingEmployee(null)
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
        <div className="data-table">
          <div className="data-table-head" style={{ gridTemplateColumns: EMPLOYEE_COLUMNS }}>
            <span>Имя</span>
            <span>Телефон</span>
            <span>Роль</span>
            <span>Склады</span>
            <span />
          </div>
          <div className="data-table-body">
            {employees.map((e, i) => {
              const editable = e.role !== 'owner'
              return (
                <button
                  key={e.id}
                  type="button"
                  className={`data-row sale-history-row-in${editable ? ' data-row-link' : ''}`}
                  style={
                    {
                      gridTemplateColumns: EMPLOYEE_COLUMNS,
                      '--row-delay': `${Math.min(i, 12) * 25}ms`,
                    } as CSSProperties
                  }
                  disabled={!editable}
                  onClick={() => editable && setEditingEmployee(e)}
                >
                  <span className="data-row-name">{e.name}</span>
                  <span className="text-muted">{e.phone}</span>
                  <span>{ROLE_LABELS[e.role]}</span>
                  <span className="text-muted">
                    {e.role === 'owner'
                      ? 'Все склады'
                      : e.warehouse_ids.map((id) => warehouseNameById.get(id) ?? id).join(', ') || '—'}
                  </span>
                  {editable ? (
                    <IconChevronRight size={16} stroke={1.8} className="data-row-chevron" />
                  ) : (
                    <span />
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function WarehouseCheckboxList({
  warehouses,
  selected,
  onChange,
}: {
  warehouses: Warehouse[]
  selected: number[]
  onChange: (ids: number[]) => void
}) {
  function toggle(id: number) {
    onChange(selected.includes(id) ? selected.filter((v) => v !== id) : [...selected, id])
  }

  return (
    <div className="stack" style={{ gap: 8 }}>
      {warehouses.map((w) => (
        <label key={w.id} className="row" style={{ gap: 8 }}>
          <input type="checkbox" checked={selected.includes(w.id)} onChange={() => toggle(w.id)} />
          {w.name}
        </label>
      ))}
    </div>
  )
}

function EmployeeForm({
  warehouses,
  employee,
  onDone,
}: {
  warehouses: Warehouse[]
  employee?: User
  onDone: () => void
}) {
  const isEdit = employee != null
  const [name, setName] = useState(employee?.name ?? '')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>(employee?.role ?? 'seller')
  const [isActive, setIsActive] = useState(employee?.is_active ?? true)
  const [warehouseIds, setWarehouseIds] = useState<number[]>(employee?.warehouse_ids ?? [])
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  // выбор склада показываем только когда складов больше одного — при одном
  // складе бэкенд привяжет сотрудника к нему автоматически, спрашивать нечего
  const needsWarehousePicker = WAREHOUSE_SCOPED_ROLES.includes(role) && warehouses.length > 1

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (needsWarehousePicker && warehouseIds.length === 0) {
      setError('Выберите хотя бы один склад')
      return
    }
    setSaving(true)
    try {
      if (isEdit && employee) {
        await updateEmployee(employee.id, {
          name,
          role,
          is_active: isActive,
          warehouse_ids: WAREHOUSE_SCOPED_ROLES.includes(role) ? warehouseIds : null,
        })
      } else {
        await createEmployee({
          name,
          phone,
          password,
          role,
          warehouse_ids: WAREHOUSE_SCOPED_ROLES.includes(role) ? warehouseIds : undefined,
        })
      }
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить сотрудника')
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
      {!isEdit && (
        <>
          <label className="field">
            Телефон
            <PhoneInput value={phone} onChange={setPhone} required />
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
        </>
      )}
      <label className="field">
        Роль
        <Select
          value={role}
          onChange={(v) => setRole(v as Role)}
          options={ASSIGNABLE_ROLES.map((value) => ({ value, label: ROLE_LABELS[value] }))}
        />
      </label>
      {needsWarehousePicker && (
        <div className="field">
          Склады
          <WarehouseCheckboxList
            warehouses={warehouses}
            selected={warehouseIds}
            onChange={setWarehouseIds}
          />
        </div>
      )}
      {isEdit && (
        <label className="row" style={{ gap: 8 }}>
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          Активен
        </label>
      )}
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : isEdit ? 'Сохранить' : 'Добавить сотрудника'}
      </Button>
    </form>
  )
}
