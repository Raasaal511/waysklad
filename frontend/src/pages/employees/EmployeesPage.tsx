import { useEffect, useState, type CSSProperties, type FormEvent } from 'react'
import { createEmployee, updateEmployee } from '../../entities/profile/api'
import type { Role, User } from '../../entities/auth/api'
import type { Warehouse } from '../../entities/inventory/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { useCatalog } from '../../app/CatalogContext'
import { Modal } from '../../shared/ui/Modal'
import { IconPlus, IconChevronRight, IconUsersGroup, IconBuildingWarehouse } from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { PhoneInput } from '../../shared/ui/PhoneInput'
import { Avatar } from '../../shared/ui/Avatar'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './EmployeesPage.module.css'

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

const ROLE_BADGE_VARIANT: Record<Role, 'accent' | 'warning' | 'default'> = {
  owner: 'accent',
  manager: 'accent',
  seller: 'default',
  storekeeper: 'default',
  analyst: 'warning',
}

export function EmployeesPage() {
  const { user } = useAuth()
  const { employees, warehouses, ensureEmployees, ensureWarehouses, refresh: refreshCatalog } = useCatalog()
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
      await Promise.all([ensureEmployees(), ensureWarehouses()])
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
      <div className={layoutStyles.stack}>
        <h2>Сотрудники</h2>
        <p className={layoutStyles.textMuted}>Доступно только владельцу и управляющему.</p>
      </div>
    )
  }

  const warehouseNameById = new Map(warehouses.map((w) => [w.id, w.name]))
  const activeCount = employees.filter((e) => e.is_active).length
  const inactiveCount = employees.length - activeCount

  return (
    <div className={layoutStyles.stack}>
      <div className={layoutStyles.sectionTitle}>
        <h2>Сотрудники</h2>
        <Button onClick={() => setShowEmployeeForm(true)}>
          <IconPlus size={16} stroke={1.8} /> Сотрудник
        </Button>
      </div>

      {!loading && employees.length > 0 && (
        <div className={`${layoutStyles.card} ${layoutStyles.cardFull}`}>
          <div className={layoutStyles.gridStats}>
            <div className={layoutStyles.stat}>
              <span className={layoutStyles.statLabel}>Всего</span>
              <span className={layoutStyles.statValue}>{employees.length}</span>
            </div>
            <div className={layoutStyles.stat}>
              <span className={layoutStyles.statLabel}>Активны</span>
              <span className={layoutStyles.statValue}>{activeCount}</span>
            </div>
            {inactiveCount > 0 && (
              <div className={layoutStyles.stat}>
                <span className={layoutStyles.statLabel}>Отключены</span>
                <span className={`${layoutStyles.statValue} ${layoutStyles.statValueWarning}`}>{inactiveCount}</span>
              </div>
            )}
            <div className={layoutStyles.stat}>
              <span className={layoutStyles.statLabel}>Складов</span>
              <span className={layoutStyles.statValue}>{warehouses.length}</span>
            </div>
          </div>
        </div>
      )}

      {showEmployeeForm && (
        <Modal title="Новый сотрудник" onClose={() => setShowEmployeeForm(false)}>
          <EmployeeForm
            warehouses={warehouses}
            onDone={() => {
              setShowEmployeeForm(false)
              refreshCatalog(['employees']).catch(() => {})
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
              refreshCatalog(['employees']).catch(() => {})
            }}
          />
        </Modal>
      )}

      {error && <p className={layoutStyles.error}>{error}</p>}
      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : employees.length === 0 ? (
        <div className={styles.emptyState}>
          <IconUsersGroup size={28} stroke={1.5} className={styles.emptyStateIcon} />
          <p className={layoutStyles.textMuted}>Кроме вас сотрудников пока нет</p>
        </div>
      ) : (
        <div className={styles.employeeGrid}>
          {employees.map((e, i) => {
            const editable = e.role !== 'owner'
            const warehouseNames =
              e.role === 'owner'
                ? 'Все склады'
                : e.warehouse_ids.map((id) => warehouseNameById.get(id) ?? id).join(', ') || 'Склад не назначен'
            return (
              <button
                key={e.id}
                type="button"
                className={`${styles.employeeCard} sale-history-row-in${editable ? ` ${styles.employeeCardLink}` : ''}${!e.is_active ? ` ${styles.employeeCardInactive}` : ''}`}
                style={{ '--row-delay': `${Math.min(i, 12) * 30}ms` } as CSSProperties}
                disabled={!editable}
                onClick={() => editable && setEditingEmployee(e)}
              >
                <Avatar name={e.name} size="lg" />
                <div className={styles.employeeBody}>
                  <div className={styles.employeeNameRow}>
                    <strong className={styles.employeeName}>{e.name}</strong>
                    {!e.is_active && <span className="badge">Отключён</span>}
                  </div>
                  <span className={layoutStyles.textMuted}>{e.phone}</span>
                  <div className={styles.employeeMetaRow}>
                    <span
                      className={[
                        'badge',
                        ROLE_BADGE_VARIANT[e.role] === 'accent' && 'accent',
                        ROLE_BADGE_VARIANT[e.role] === 'warning' && 'warning',
                      ]
                        .filter(Boolean)
                        .join(' ')}
                    >
                      {ROLE_LABELS[e.role]}
                    </span>
                    <span className={styles.employeeWarehouses}>
                      <IconBuildingWarehouse size={14} stroke={1.8} />
                      {warehouseNames}
                    </span>
                  </div>
                </div>
                {editable && <IconChevronRight size={18} stroke={1.8} className={styles.employeeChevron} />}
              </button>
            )
          })}
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
    <div className={layoutStyles.stack} style={{ gap: 8 }}>
      {warehouses.map((w) => (
        <label key={w.id} className={layoutStyles.row} style={{ gap: 8 }}>
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
    <form className={layoutStyles.form} onSubmit={handleSubmit}>
      <label className={layoutStyles.field}>
        Имя
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      {!isEdit && (
        <>
          <label className={layoutStyles.field}>
            Телефон
            <PhoneInput value={phone} onChange={setPhone} required />
          </label>
          <label className={layoutStyles.field}>
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
      <label className={layoutStyles.field}>
        Роль
        <Select
          value={role}
          onChange={(v) => setRole(v as Role)}
          options={ASSIGNABLE_ROLES.map((value) => ({ value, label: ROLE_LABELS[value] }))}
        />
      </label>
      {needsWarehousePicker && (
        <div className={layoutStyles.field}>
          Склады
          <WarehouseCheckboxList
            warehouses={warehouses}
            selected={warehouseIds}
            onChange={setWarehouseIds}
          />
        </div>
      )}
      {isEdit && (
        <label className={layoutStyles.row} style={{ gap: 8 }}>
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          Активен
        </label>
      )}
      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : isEdit ? 'Сохранить' : 'Добавить сотрудника'}
      </Button>
    </form>
  )
}
