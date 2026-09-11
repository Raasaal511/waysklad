import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { IconChevronLeft } from '@tabler/icons-react'
import { searchClients, type Client } from '../../entities/counterparty/api'
import { NewSaleForm } from './NewSaleForm'
import layoutStyles from '../../shared/ui/Layout.module.css'

export function SaleNewPage() {
  const navigate = useNavigate()
  const [clients, setClients] = useState<Client[]>([])

  useEffect(() => {
    searchClients()
      .then(setClients)
      .catch(() => {})
  }, [])

  return (
    <div className={layoutStyles.stack}>
      <Link to="/" className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> Все продажи
      </Link>
      <NewSaleForm
        clients={clients}
        onClientsChange={setClients}
        onClose={() => navigate('/')}
        onDone={(sale) => navigate(`/sales/${sale.id}`, { replace: true })}
      />
    </div>
  )
}
