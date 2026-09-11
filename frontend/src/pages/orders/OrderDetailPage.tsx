import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { IconChevronLeft } from '@tabler/icons-react'
import { getOrder, type Order } from '../../entities/order/api'
import { searchClients, type Client } from '../../entities/counterparty/api'
import { useCatalog } from '../../app/CatalogContext'
import { useAuth } from '../../app/AuthContext'
import { ApiError } from '../../shared/api/client'
import { OrderDetailView } from './OrderDetailView'
import layoutStyles from '../../shared/ui/Layout.module.css'

export function OrderDetailPage() {
  const { id } = useParams<{ id: string }>()
  const orderId = Number(id)
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = user?.role === 'owner' || user?.role === 'manager' || user?.role === 'seller'

  const { products, units, warehouses, stock, ensureProducts, ensureUnits, ensureWarehouses, ensureStock } =
    useCatalog()

  const [order, setOrder] = useState<Order | null>(null)
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    ensureProducts().catch(() => {})
    ensureUnits().catch(() => {})
    ensureWarehouses().catch(() => {})
    ensureStock().catch(() => {})
    searchClients()
      .then(setClients)
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!Number.isFinite(orderId) || orderId <= 0) {
      setOrder(null)
      setError('Заказ не найден')
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    getOrder(orderId)
      .then((o) => {
        if (!cancelled) setOrder(o)
      })
      .catch((err) => {
        if (cancelled) return
        setOrder(null)
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить заказ')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [orderId])

  if (!loading && !order) {
    return (
      <div className={layoutStyles.stack}>
        <Link to="/orders" className={layoutStyles.backLink}>
          <IconChevronLeft size={16} stroke={1.8} /> Все заказы
        </Link>
        <p className={layoutStyles.error}>{error ?? 'Заказ не найден'}</p>
      </div>
    )
  }

  return (
    <div className={layoutStyles.stack}>
      <Link to="/orders" className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> Все заказы
      </Link>

      {loading || !order ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : (
        <OrderDetailView
          order={order}
          products={products}
          units={units}
          clients={clients}
          warehouses={warehouses}
          stock={stock}
          canManage={canManage}
          onDone={() => navigate('/orders')}
          onUpdated={() => {
            getOrder(orderId)
              .then(setOrder)
              .catch(() => {})
          }}
        />
      )}
    </div>
  )
}
