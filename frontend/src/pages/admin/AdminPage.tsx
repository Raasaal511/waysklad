import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
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
  type AdminMetricsPoint,
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
    <div className={styles.statusLayout}>
      <section className={styles.gaugeRow}>
        <GaugeCard label="Процессор" percent={status.cpu_percent} />
        <GaugeCard
          label="Память"
          percent={status.memory_percent}
          note={`${formatMb(status.memory_used_mb)} из ${formatMb(status.memory_total_mb)}`}
        />
        <GaugeCard
          label="Диск"
          percent={status.disk_percent}
          note={`${status.disk_used_gb} ГБ из ${status.disk_total_gb} ГБ`}
        />
      </section>

      {status.history.length > 1 && (
        <section className={styles.historyCard}>
          <div className={styles.historyHead}>
            <span className={styles.cardLabel}>Нагрузка за последний час</span>
            <div className={styles.historyLegend}>
              <span className={styles.legendDot} data-series="cpu" />
              CPU
              <span className={styles.legendDot} data-series="memory" />
              Память
            </div>
          </div>
          <HistoryChart points={status.history} />
        </section>
      )}

      <section className={styles.pillRow}>
        <HealthPill label="База данных" ok={status.db_connected} />
        <HealthPill label="Redis" ok={status.redis_connected} />
      </section>

      <section className={styles.grid}>
        <StatusCard label="Пользователи" value={String(status.active_users)} />
        <StatusCard label="Магазины" value={String(status.active_tenants)} />
        <StatusCard
          label="Онлайн сейчас"
          value={String(status.online_now)}
          note={status.online_now_note}
        />
      </section>

      {status.recent_tenants.length > 0 && (
        <section>
          <h3 className={styles.sectionTitle}>Недавно зарегистрированные магазины</h3>
          <ul className={styles.recentList}>
            {status.recent_tenants.map((t) => (
              <li key={t.id} className={styles.recentItem}>
                <Link to={`/admin/tenants/${t.id}`} className={styles.recentName}>
                  {t.name}
                </Link>
                <span className={styles.recentSlug}>{t.slug ?? '—'}</span>
                <time className={styles.recentTime}>{formatDateTime(t.created_at)}</time>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function HistoryChart({ points }: { points: AdminMetricsPoint[] }) {
  const width = 600
  const height = 80
  const pad = 4

  function toPath(values: number[]): string {
    if (values.length < 2) return ''
    const step = (width - pad * 2) / (values.length - 1)
    return values
      .map((v, i) => {
        const x = pad + i * step
        const y = height - pad - (Math.min(Math.max(v, 0), 100) / 100) * (height - pad * 2)
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  }

  const cpuPath = toPath(points.map((p) => p.cpu_percent))
  const memPath = toPath(points.map((p) => p.memory_percent))

  return (
    <svg
      className={styles.historyChart}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="График нагрузки CPU и памяти за последний час"
    >
      <path d={memPath} className={styles.historyLineMemory} fill="none" />
      <path d={cpuPath} className={styles.historyLineCpu} fill="none" />
    </svg>
  )
}

function HealthPill({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className={styles.healthPill} data-ok={ok}>
      <span className={styles.healthDot} />
      <span>{label}</span>
      <strong>{ok ? 'в норме' : 'недоступен'}</strong>
    </div>
  )
}

function formatMb(mb: number): string {
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} ГБ` : `${mb} МБ`
}

function gaugeLevel(percent: number): 'ok' | 'warn' | 'danger' {
  if (percent >= 90) return 'danger'
  if (percent >= 70) return 'warn'
  return 'ok'
}

function GaugeCard({ label, percent, note }: { label: string; percent: number; note?: string }) {
  const level = gaugeLevel(percent)
  return (
    <div className={styles.gaugeCard} data-level={level}>
      <div className={styles.gaugeHead}>
        <span className={styles.cardLabel}>{label}</span>
        <span className={styles.gaugeValue}>{percent.toFixed(0)}%</span>
      </div>
      <div className={styles.gaugeTrack}>
        <div
          className={styles.gaugeFill}
          data-level={level}
          style={{ width: `${Math.min(Math.max(percent, 0), 100)}%` }}
        />
      </div>
      {note && <span className={styles.note}>{note}</span>}
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

type TenantStatusFilter = 'all' | 'active' | 'suspended'

function AdminTenantsPanel({ logout }: { logout: () => void }) {
  const [tenants, setTenants] = useState<AdminTenantListItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<TenantStatusFilter>('all')

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

  const normalizedQuery = query.trim().toLowerCase()
  const filtered = tenants.filter((t) => {
    if (statusFilter === 'active' && t.is_suspended) return false
    if (statusFilter === 'suspended' && !t.is_suspended) return false
    if (!normalizedQuery) return true
    return (
      t.name.toLowerCase().includes(normalizedQuery) ||
      (t.slug ?? '').toLowerCase().includes(normalizedQuery)
    )
  })

  return (
    <div className={styles.tenantsLayout}>
      <div className={styles.tenantsToolbar}>
        <input
          type="search"
          className={styles.searchInput}
          placeholder="Поиск по названию или slug…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className={styles.filterTabs}>
          <FilterTab active={statusFilter === 'all'} onClick={() => setStatusFilter('all')}>
            Все · {tenants.length}
          </FilterTab>
          <FilterTab active={statusFilter === 'active'} onClick={() => setStatusFilter('active')}>
            Активные · {tenants.filter((t) => !t.is_suspended).length}
          </FilterTab>
          <FilterTab
            active={statusFilter === 'suspended'}
            onClick={() => setStatusFilter('suspended')}
          >
            Заблокированные · {tenants.filter((t) => t.is_suspended).length}
          </FilterTab>
        </div>
      </div>

      {filtered.length === 0 ? (
        <p className={layoutStyles.textMuted}>Ничего не найдено</p>
      ) : (
        <div className={styles.tenantGrid}>
          {filtered.map((t) => (
            <Link key={t.id} to={`/admin/tenants/${t.id}`} className={styles.tenantCard}>
              <div className={styles.tenantCardHead}>
                <strong>{t.name}</strong>
                <span className={t.is_suspended ? styles.badgeDanger : styles.badgeOk}>
                  {t.is_suspended ? 'заблокирован' : 'активен'}
                </span>
              </div>
              <span className={styles.tenantSlug}>{t.slug ? `/store/${t.slug}` : 'без slug'}</span>
              <div className={styles.tenantCardFoot}>
                <span className={t.storefront_enabled ? undefined : styles.tenantDim}>
                  {t.storefront_enabled ? 'Витрина включена' : 'Витрина выключена'}
                </span>
                <time>{formatDateTime(t.created_at)}</time>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function FilterTab({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button type="button" className={styles.filterTab} data-active={active} onClick={onClick}>
      {children}
    </button>
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
          <time className={styles.errorTime}>{formatLogTime(e.timestamp)}</time>
          <span className={styles.errorMethod}>{e.method}</span>
          <span className={styles.errorLine}>
            <span className={styles.errorPath}>{e.path}</span>
            {' — '}
            <span className={styles.errorMessage}>{e.message}</span>
          </span>
        </li>
      ))}
    </ul>
  )
}

function formatLogTime(value: string): string {
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
