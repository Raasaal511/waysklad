/**
 * Карточка магазина. Перенесена из прежней страницы; активность, состав и
 * график — следующий шаг (B4).
 */
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  getAdminTenant,
  suspendAdminTenant,
  unsuspendAdminTenant,
  type AdminTenantDetail,
} from '../../../entities/admin/api'
import { Button } from '../../../shared/ui/Button'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import layoutStyles from '../../../shared/ui/Layout.module.css'
import { handleAdminError } from '../shared'
import styles from '../AdminPage.module.css'

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

export function TenantDetailSection({ logout, refreshKey, onLoaded }: SectionProps) {
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
    } finally {
      onLoaded()
    }
  }, [id, logout, onLoaded])

  useEffect(() => {
    load()
  }, [load, refreshKey])

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
