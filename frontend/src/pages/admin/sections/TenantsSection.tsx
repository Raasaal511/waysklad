import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { listAdminTenants, type AdminTenantListItem } from '../../../entities/admin/api'
import { formatExactDateTime, formatRelativeTime } from '../../../shared/lib/format'
import layoutStyles from '../../../shared/ui/Layout.module.css'
import { useAutoRefresh } from '../AdminLayout'
import { handleAdminError } from '../shared'
import styles from '../AdminPage.module.css'

type TenantStatusFilter = 'all' | 'active' | 'suspended'

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

interface SectionProps {
  logout: () => void
  refreshKey: number
  onLoaded: () => void
}

export function TenantsSection({ logout, refreshKey, onLoaded }: SectionProps) {
  const [tenants, setTenants] = useState<AdminTenantListItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<TenantStatusFilter>('all')

  const load = useCallback(async () => {
    try {
      const data = await listAdminTenants()
      setTenants(data.tenants)
      setError(null)
    } catch (err) {
      setError(handleAdminError(err, logout))
    } finally {
      setLoading(false)
      onLoaded()
    }
  }, [logout, onLoaded])

  useEffect(() => {
    load()
  }, [load, refreshKey])

  useAutoRefresh(load)

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
              <span
                className={styles.tenantSlug}
                title={formatExactDateTime(t.owner_last_seen_at) || undefined}
              >
                Владелец был в сети {formatRelativeTime(t.owner_last_seen_at)}
              </span>
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
