import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import {
  adminLogin,
  clearAdminToken,
  getAdminErrorLogs,
  getAdminStatus,
  getAdminTenant,
  listAdminTenants,
  loadAdminToken,
  saveAdminToken,
  suspendAdminTenant,
  unsuspendAdminTenant,
  type AdminErrorLog,
  type AdminStatus,
  type AdminTenantDetail,
  type AdminTenantListItem,
} from '../../entities/admin/api'
import { ApiError } from '../../shared/api/client'
import { Button } from '../../shared/ui/Button'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './AdminPage.module.css'

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function useAdminAuth() {
  const [token, setToken] = useState(() => loadAdminToken())

  function login(accessToken: string) {
    saveAdminToken(accessToken)
    setToken(accessToken)
  }

  function logout() {
    clearAdminToken()
    setToken(null)
  }

  return { token, login, logout }
}

function handleAdminError(err: unknown, logout: () => void): string {
  if (err instanceof ApiError && err.status === 401) {
    logout()
    return 'Сессия истекла — войдите снова'
  }
  return err instanceof ApiError ? err.message : 'Ошибка запроса'
}

export function AdminPage() {
  const auth = useAdminAuth()

  if (!auth.token) {
    return <AdminLogin onSuccess={auth.login} />
  }

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>WaySklad</p>
          <h1>Админ-панель</h1>
        </div>
        <nav className={styles.nav}>
          <Link to="/admin">Статус</Link>
          <Link to="/admin/tenants">Магазины</Link>
          <Link to="/admin/errors">Ошибки</Link>
          <button type="button" className={styles.logout} onClick={auth.logout}>
            Выйти
          </button>
        </nav>
      </header>
      <main className={styles.main}>
        <Routes>
          <Route index element={<AdminStatusPanel logout={auth.logout} />} />
          <Route path="tenants" element={<AdminTenantsPanel logout={auth.logout} />} />
          <Route path="tenants/:id" element={<AdminTenantDetailPanel logout={auth.logout} />} />
          <Route path="errors" element={<AdminErrorsPanel logout={auth.logout} />} />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Routes>
      </main>
    </div>
  )
}

function AdminLogin({ onSuccess }: { onSuccess: (token: string) => void }) {
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await adminLogin(login.trim(), password)
      onSuccess(result.access_token)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось войти')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.loginShell}>
      <form className={styles.loginCard} onSubmit={handleSubmit}>
        <h1>Админ</h1>
        <p className={layoutStyles.textMuted}>Приватный вход в панель платформы</p>
        <label className={styles.field}>
          Логин
          <input value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" required />
        </label>
        <label className={styles.field}>
          Пароль
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && <p className={layoutStyles.error}>{error}</p>}
        <Button type="submit" disabled={loading}>
          {loading ? 'Вход…' : 'Войти'}
        </Button>
      </form>
    </div>
  )
}

function AdminStatusPanel({ logout }: { logout: () => void }) {
  const [status, setStatus] = useState<AdminStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setStatus(await getAdminStatus())
      setError(null)
    } catch (err) {
      setError(handleAdminError(err, logout))
    }
  }, [logout])

  useEffect(() => {
    load()
    const id = window.setInterval(load, 8000)
    return () => window.clearInterval(id)
  }, [load])

  if (error) return <p className={layoutStyles.error}>{error}</p>
  if (!status) return <p className={layoutStyles.textMuted}>Загрузка…</p>

  return (
    <div className={styles.grid}>
      <StatusCard label="БД" value={status.db_connected ? 'OK' : 'Нет'} ok={status.db_connected} />
      <StatusCard label="Redis" value={status.redis_connected ? 'OK' : 'Нет'} ok={status.redis_connected} />
      <StatusCard label="Пользователи" value={String(status.active_users)} />
      <StatusCard label="Магазины" value={String(status.active_tenants)} />
      <StatusCard
        label="Онлайн сейчас"
        value={String(status.online_now)}
        note={status.online_now_note}
      />
    </div>
  )
}

function StatusCard({
  label,
  value,
  ok,
  note,
}: {
  label: string
  value: string
  ok?: boolean
  note?: string
}) {
  return (
    <div className={styles.card}>
      <span className={styles.cardLabel}>{label}</span>
      <strong className={ok === false ? styles.bad : undefined}>{value}</strong>
      {note && <span className={styles.note} title={note}>{note}</span>}
    </div>
  )
}

function AdminTenantsPanel({ logout }: { logout: () => void }) {
  const [tenants, setTenants] = useState<AdminTenantListItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const data = await listAdminTenants()
        if (!cancelled) setTenants(data.tenants)
      } catch (err) {
        if (!cancelled) setError(handleAdminError(err, logout))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [logout])

  if (loading) return <p className={layoutStyles.textMuted}>Загрузка…</p>
  if (error) return <p className={layoutStyles.error}>{error}</p>

  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>ID</th>
            <th>Название</th>
            <th>Slug</th>
            <th>Витрина</th>
            <th>Статус</th>
            <th>Создан</th>
          </tr>
        </thead>
        <tbody>
          {tenants.map((t) => (
            <tr key={t.id}>
              <td>{t.id}</td>
              <td>
                <Link to={`/admin/tenants/${t.id}`}>{t.name}</Link>
              </td>
              <td>{t.slug ?? '—'}</td>
              <td>{t.storefront_enabled ? 'да' : 'нет'}</td>
              <td>
                <span className={t.is_suspended ? styles.badgeDanger : styles.badgeOk}>
                  {t.is_suspended ? 'заблокирован' : 'активен'}
                </span>
              </td>
              <td>{formatDateTime(t.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AdminTenantDetailPanel({ logout }: { logout: () => void }) {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [tenant, setTenant] = useState<AdminTenantDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirmSuspend, setConfirmSuspend] = useState(false)

  const load = useCallback(async () => {
    try {
      setTenant(await getAdminTenant(Number(id)))
      setError(null)
    } catch (err) {
      setError(handleAdminError(err, logout))
    }
  }, [id, logout])

  useEffect(() => {
    load()
  }, [load])

  if (error) return <p className={layoutStyles.error}>{error}</p>
  if (!tenant) return <p className={layoutStyles.textMuted}>Загрузка…</p>

  return (
    <div className={styles.detail}>
      <button type="button" className={styles.backLink} onClick={() => navigate('/admin/tenants')}>
        ← К списку
      </button>
      <div className={styles.detailHead}>
        <div>
          <h2>{tenant.name}</h2>
          <p className={layoutStyles.textMuted}>
            #{tenant.id}
            {tenant.slug ? ` · /store/${tenant.slug}` : ''}
          </p>
        </div>
        <Button
          variant={tenant.is_suspended ? 'primary' : 'danger'}
          onClick={() => {
            if (tenant.is_suspended) {
              unsuspendAdminTenant(tenant.id)
                .then(setTenant)
                .catch((err) => setError(handleAdminError(err, logout)))
            } else {
              setConfirmSuspend(true)
            }
          }}
        >
          {tenant.is_suspended ? 'Разблокировать' : 'Заблокировать'}
        </Button>
      </div>

      <div className={styles.metaGrid}>
        <div>
          <span className={layoutStyles.textMuted}>Статус</span>
          <strong>{tenant.is_suspended ? 'Заблокирован' : 'Активен'}</strong>
        </div>
        <div>
          <span className={layoutStyles.textMuted}>Витрина</span>
          <strong>{tenant.storefront_enabled ? 'включена' : 'выключена'}</strong>
        </div>
        <div>
          <span className={layoutStyles.textMuted}>Владелец</span>
          <strong>
            {tenant.owner ? `${tenant.owner.name} · ${tenant.owner.phone}` : '—'}
          </strong>
        </div>
        <div>
          <span className={layoutStyles.textMuted}>Пользователи</span>
          <strong>{tenant.users_count}</strong>
        </div>
        <div>
          <span className={layoutStyles.textMuted}>Товары</span>
          <strong>{tenant.products_count}</strong>
        </div>
        <div>
          <span className={layoutStyles.textMuted}>Склады</span>
          <strong>{tenant.warehouses_count}</strong>
        </div>
        <div>
          <span className={layoutStyles.textMuted}>Создан</span>
          <strong>{formatDateTime(tenant.created_at)}</strong>
        </div>
        <div>
          <span className={layoutStyles.textMuted}>Последняя продажа</span>
          <strong>{tenant.last_sale_at ? formatDateTime(tenant.last_sale_at) : '—'}</strong>
        </div>
      </div>

      {confirmSuspend && (
        <ConfirmDialog
          title="Заблокировать магазин?"
          message={`Владелец и сотрудники «${tenant.name}» сразу потеряют доступ. Витрина перестанет открываться.`}
          confirmLabel="Заблокировать"
          danger
          onClose={() => setConfirmSuspend(false)}
          onConfirm={async () => {
            const updated = await suspendAdminTenant(tenant.id)
            setTenant(updated)
          }}
        />
      )}
    </div>
  )
}

function AdminErrorsPanel({ logout }: { logout: () => void }) {
  const [errors, setErrors] = useState<AdminErrorLog[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const data = await getAdminErrorLogs(100)
        if (!cancelled) setErrors(data.errors)
      } catch (err) {
        if (!cancelled) setError(handleAdminError(err, logout))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [logout])

  if (loading) return <p className={layoutStyles.textMuted}>Загрузка…</p>
  if (error) return <p className={layoutStyles.error}>{error}</p>
  if (errors.length === 0) return <p className={layoutStyles.textMuted}>Пока нет записанных ошибок</p>

  return (
    <ul className={styles.errorList}>
      {errors.map((e, i) => (
        <li key={`${e.timestamp}-${i}`} className={styles.errorItem}>
          <div className={styles.errorMeta}>
            <time>{formatDateTime(e.timestamp)}</time>
            <code>
              {e.method} {e.path}
            </code>
          </div>
          <strong>
            {e.error_type}: {e.message}
          </strong>
        </li>
      ))}
    </ul>
  )
}
