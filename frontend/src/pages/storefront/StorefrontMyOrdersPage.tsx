import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { IconChevronLeft, IconLogout } from '@tabler/icons-react'
import {
  clearCustomerToken,
  listMyStorefrontRequests,
  loadCustomerToken,
  type CustomerRequest,
} from '../../entities/auth/customerApi'
import { ApiError } from '../../shared/api/client'
import { Button } from '../../shared/ui/Button'
import { CustomerLoginModal, notifyCustomerAuthChanged } from './CustomerLoginModal'
import styles from './Storefront.module.css'

const STATUS_LABEL: Record<CustomerRequest['status'], string> = {
  new: 'Новый',
  accepted: 'Подтверждён',
  rejected: 'Отклонён',
}

export function StorefrontMyOrdersPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const [token, setToken] = useState(() => loadCustomerToken())
  const [showLogin, setShowLogin] = useState(!loadCustomerToken())
  const [items, setItems] = useState<CustomerRequest[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setItems([])
      return
    }
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const list = await listMyStorefrontRequests()
        if (!cancelled) setItems(list)
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) {
          clearCustomerToken()
          notifyCustomerAuthChanged()
          setToken(null)
          setShowLogin(true)
          return
        }
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить заказы')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [token])

  return (
    <div className={styles.shell}>
      <header className={styles.headerCompact}>
        <Link to={`/store/${slug}`} className={styles.back}>
          <IconChevronLeft size={16} /> К каталогу
        </Link>
      </header>

      <main className={styles.cartPage}>
        <div className={styles.myOrdersHead}>
          <div>
            <h1>Мои заказы</h1>
            <p className={styles.muted}>Заказы во всех магазинах ВайСклада с вашего аккаунта.</p>
          </div>
          {token && (
            <button
              type="button"
              className={styles.iconGhost}
              aria-label="Выйти"
              onClick={() => {
                clearCustomerToken()
                notifyCustomerAuthChanged()
                setToken(null)
              }}
            >
              <IconLogout size={18} stroke={1.8} />
            </button>
          )}
        </div>

        {!token && (
          <div className={styles.emptyState}>
            <p>Войдите, чтобы увидеть историю заказов.</p>
            <Button type="button" onClick={() => setShowLogin(true)}>
              Войти
            </Button>
          </div>
        )}

        {token && loading && <p className={styles.muted}>Загрузка…</p>}
        {token && error && <p className={styles.error}>{error}</p>}

        {token && !loading && !error && items.length === 0 && (
          <div className={styles.emptyState}>
            <p>Пока нет заказов</p>
            <Link to={`/store/${slug}`}>
              <Button>В каталог</Button>
            </Link>
          </div>
        )}

        {token && items.length > 0 && (
          <ul className={styles.myOrdersList}>
            {items.map((req) => (
              <li key={req.id} className={styles.myOrderCard}>
                <div className={styles.myOrderHead}>
                  <strong>{req.shop_name}</strong>
                  <span className={styles.myOrderStatus} data-status={req.status}>
                    {STATUS_LABEL[req.status]}
                  </span>
                </div>
                <p className={styles.muted}>
                  {req.customer_name}
                  {req.customer_phone ? ` · ${req.customer_phone}` : ''}
                </p>
                <p>
                  {req.lines.length} поз.
                  {req.note ? ` · ${req.note}` : ''}
                </p>
                {req.insufficient_stock_at_request && (
                  <p className={styles.muted}>На момент заказа часть позиций могла быть без остатка</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </main>

      {showLogin && (
        <CustomerLoginModal
          onClose={() => setShowLogin(false)}
          onSuccess={(accessToken) => {
            setToken(accessToken)
            notifyCustomerAuthChanged()
            setShowLogin(false)
          }}
        />
      )}
    </div>
  )
}
