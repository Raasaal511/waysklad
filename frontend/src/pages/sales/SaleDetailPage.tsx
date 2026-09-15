import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { IconChevronLeft } from '@tabler/icons-react'
import { getSale, type Sale } from '../../entities/sale/api'
import { searchClients, type Client } from '../../entities/counterparty/api'
import { useCatalog } from '../../app/CatalogContext'
import { ApiError } from '../../shared/api/client'
import { SaleDetailView } from './SaleDetailView'
import layoutStyles from '../../shared/ui/Layout.module.css'

export function SaleDetailPage() {
  const { id } = useParams<{ id: string }>()
  const saleId = Number(id)
  const navigate = useNavigate()
  const { warehouses, ensureWarehouses } = useCatalog()

  const [sale, setSale] = useState<Sale | null>(null)
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    ensureWarehouses().catch(() => {})
    searchClients()
      .then(setClients)
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!Number.isFinite(saleId) || saleId <= 0) {
      setSale(null)
      setError('Продажа не найдена')
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    getSale(saleId)
      .then((s) => {
        if (!cancelled) setSale(s)
      })
      .catch((err) => {
        if (cancelled) return
        setSale(null)
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить продажу')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [saleId])

  if (!loading && !sale) {
    return (
      <div className={layoutStyles.stack}>
        <Link to="/" className={layoutStyles.backLink}>
          <IconChevronLeft size={16} stroke={1.8} /> Все продажи
        </Link>
        <p className={layoutStyles.error}>{error ?? 'Продажа не найдена'}</p>
      </div>
    )
  }

  return (
    <div className={layoutStyles.stack}>
      <Link to="/" className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> Все продажи
      </Link>

      {loading || !sale ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : (
        <SaleDetailView
          sale={sale}
          warehouses={warehouses}
          clients={clients}
          onDone={() => navigate('/')}
          onUpdated={() => {
            getSale(saleId)
              .then(setSale)
              .catch(() => {})
          }}
        />
      )}
    </div>
  )
}
