import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { IconChevronLeft } from '@tabler/icons-react'
import { searchClients, type Client } from '../../entities/counterparty/api'
import { useCatalog } from '../../app/CatalogContext'
import { ApiError } from '../../shared/api/client'
import { IssueDebtForm } from './IssueDebtForm'
import layoutStyles from '../../shared/ui/Layout.module.css'

export function DebtNewPage() {
  const navigate = useNavigate()
  const { suppliers, ensureSuppliers } = useCatalog()
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([searchClients(), ensureSuppliers()])
      .then(([clientList]) => {
        if (!cancelled) setClients(clientList)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Не удалось загрузить данные')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className={layoutStyles.stack}>
      <Link to="/debts" className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> Все долги
      </Link>

      <div className={layoutStyles.sectionTitle}>
        <h2>Выдать долг</h2>
      </div>

      {error && <p className={layoutStyles.error}>{error}</p>}

      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : (
        <IssueDebtForm
          clients={clients}
          onClientCreated={(client) => setClients((prev) => [...prev, client])}
          suppliers={suppliers}
          onDone={(debtId) => {
            navigate(debtId != null ? `/debts/${debtId}` : '/debts', { replace: true })
          }}
        />
      )}
    </div>
  )
}
