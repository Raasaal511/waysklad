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
import { IconButton } from '../../shared/ui/IconButton'
import { Select } from '../../shared/ui/Select'
import { PhoneInput } from '../../shared/ui/PhoneInput'
import { Avatar } from '../../shared/ui/Avatar'
import { generatePassword } from '../../shared/lib/password'
import layoutStyles from '../../shared/ui/Layout.module.css'
import { CredentialsModal, PasswordField, type Credentials } from './EmployeeCredentials'
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

// Тот же лимит, что на сервере (domain/identity/entities.py MAX_EMPLOYEES):
// включённые сотрудники без владельца.
const MAX_EMPLOYEES = 10

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
  const [credentials, setCredentials] = useState<{ title: string; data: Credentials } | null>(null)

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
  const staff = employees.filter((e) => e.role !== 'owner')
  const activeCount = staff.filter((e) => e.is_active).length
  const inactiveCount = staff.length - activeCount
  const atLimit = activeCount >= MAX_EMPLOYEES

  return (
    <div className={layoutStyles.stack}>
      <div className={layoutStyles.sectionTitle}>
        <h2>Сотрудники</h2>
        <div className={layoutStyles.pageTitleActions}>
          <div className={layoutStyles.pageTitleActionsDesktop}>
            <Button onClick={() => setShowEmployeeForm(true)} disabled={atLimit}>
              <IconPlus size={16} stroke={1.8} /> Сотрудник
            </Button>
          </div>
          <div className={layoutStyles.pageTitleActionsMobile}>
            <IconButton
              variant="accent"
              size="lg"
              aria-label="Добавить сотрудника"
              onClick={() => setShowEmployeeForm(true)}
              disabled={atLimit}
            >
              <IconPlus size={20} stroke={2} />
            </IconButton>
          </div>
        </div>
      </div>

      {!loading && employees.length > 0 && (
        <div className={`${layoutStyles.card} ${layoutStyles.cardFull}`}>
          <div className={layoutStyles.gridStats}>
            <div className={layoutStyles.stat}>
              <span className={layoutStyles.statLabel}>Сотрудников</span>
              <span className={[layoutStyles.statValue, atLimit && layoutStyles.statValueWarning].filter(Boolean).join(' ')}>
                {activeCount} <span className={styles.statOf}>из {MAX_EMPLOYEES}</span>
              </span>
            </div>
            {inactiveCount > 0 && (
              <div className={layoutStyles.stat}>
                <span className={layoutStyles.statLabel}>Отключены</span>
                <span className={layoutStyles.statValue}>{inactiveCount}</span>
              </div>
            )}
            <div className={layoutStyles.stat}>
              <span className={layoutStyles.statLabel}>Складов</span>
              <span className={layoutStyles.statValue}>{warehouses.length}</span>
            </div>
          </div>
          {atLimit && (
            <p className={styles.limitNote}>
              Это максимум. Чтобы добавить нового, отключите кого-то в его карточке.
            </p>
          )}
        </div>
      )}

      {showEmployeeForm && (
        <Modal title="Новый сотрудник" onClose={() => setShowEmployeeForm(false)}>
          <EmployeeForm
            warehouses={warehouses}
            onDone={(data) => {
              setShowEmployeeForm(false)
              if (data) setCredentials({ title: 'Сотрудник добавлен', data })
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
            onDone={(data) => {
              setEditingEmployee(null)
              if (data) setCredentials({ title: 'Пароль изменён', data })
              refreshCatalog(['employees']).catch(() => {})
            }}
          />
        </Modal>
      )}

      {credentials && (
        <CredentialsModal
          title={credentials.title}
          credentials={credentials.data}
          onClose={() => setCredentials(null)}
        />
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
  /** credentials — только если появился пароль, который надо передать сотруднику */
  onDone: (credentials?: Credentials) => void
}) {
  const isEdit = employee != null
  const [name, setName] = useState(employee?.name ?? '')
  const [phone, setPhone] = useState('')
  // новый сотрудник — пароль уже придуман; в карточке — null, пока не нажали «Задать новый пароль»
  const [password, setPassword] = useState<string | null>(employee ? null : generatePassword())
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
        const saved = await updateEmployee(employee.id, {
          name,
          role,
          is_active: isActive,
          warehouse_ids: WAREHOUSE_SCOPED_ROLES.includes(role) ? warehouseIds : null,
          ...(password ? { password } : {}),
        })
        onDone(
          password
            ? { name: saved.name, roleLabel: ROLE_LABELS[saved.role], phone: saved.phone, password }
            : undefined,
        )
      } else {
        const created = await createEmployee({
          name,
          phone,
          password: password ?? '',
          role,
          warehouse_ids: WAREHOUSE_SCOPED_ROLES.includes(role) ? warehouseIds : undefined,
        })
        onDone({ name: created.name, roleLabel: ROLE_LABELS[created.role], phone: created.phone, password: password ?? '' })
      }
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
          <PasswordField value={password ?? ''} onChange={setPassword} />
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
      {isEdit &&
        (password === null ? (
          <button type="button" className={styles.resetPassword} onClick={() => setPassword(generatePassword())}>
            Сотрудник забыл пароль? Задать новый
          </button>
        ) : (
          <PasswordField label="Новый пароль" value={password} onChange={setPassword} />
        ))}
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
