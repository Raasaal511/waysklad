import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { IconChevronLeft } from '@tabler/icons-react'
import { searchClients, type Client } from '../../entities/counterparty/api'
import { useCatalog } from '../../app/CatalogContext'
import { NewOrderForm } from './NewOrderForm'
import layoutStyles from '../../shared/ui/Layout.module.css'

export function OrderNewPage() {
  const navigate = useNavigate()
  const { products, units, warehouses, stock, ensureProducts, ensureUnits, ensureWarehouses, ensureStock } =
    useCatalog()
  const [clients, setClients] = useState<Client[]>([])

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

  return (
    <div className={layoutStyles.stack}>
      <Link to="/orders" className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> Все заказы
      </Link>
      <NewOrderForm
        products={products}
        units={units}
        clients={clients}
        warehouses={warehouses}
        stock={stock}
        onDone={(order) => navigate(`/orders/${order.id}`, { replace: true })}
      />
    </div>
  )
}
