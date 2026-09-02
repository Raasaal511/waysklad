import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getDebt, type Debt } from '../../entities/debt/api'
import { searchClients, type Client } from '../../entities/counterparty/api'
import { getSale, type Sale } from '../../entities/sale/api'
import { listDocuments, type DocumentHistoryEntry } from '../../entities/inventory/api'
import { DebtCard } from '../../entities/debt/DebtCard'
import { ApiError } from '../../shared/api/client'
import { useCatalog } from '../../app/CatalogContext'
import { IconChevronLeft } from '@tabler/icons-react'
import layoutStyles from '../../shared/ui/Layout.module.css'

export function DebtDetailPage() {
  const { id } = useParams<{ id: string }>()
  const debtId = Number(id)
  const { products, units, suppliers, ensureProducts, ensureUnits, ensureSuppliers } = useCatalog()

  const [debt, setDebt] = useState<Debt | null>(null)
  const [clients, setClients] = useState<Client[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sale, setSale] = useState<Sale | null>(null)
  const [receiptDocument, setReceiptDocument] = useState<DocumentHistoryEntry | null>(null)

  // При быстром переключении между долгами (например, из списка) более старый
  // ответ getDebt(prevId) может прийти позже нового — currentIdRef защищает от
  // перезаписи состояния устаревшими данными чужого долга.
  const currentIdRef = useRef(debtId)

  async function load() {
    const requestedId = debtId
    currentIdRef.current = requestedId
    setLoading(true)
    try {
      const [d, clientList] = await Promise.all([
        getDebt(debtId),
        searchClients('', true),
        ensureSuppliers(),
        ensureProducts(),
        ensureUnits(),
      ])
      if (currentIdRef.current !== requestedId) return
      setDebt(d)
      setClients(clientList)
      if (d.sale_id != null) {
        const s = await getSale(d.sale_id)
        if (currentIdRef.current !== requestedId) return
        setSale(s)
        setReceiptDocument(null)
      } else if (d.receipt_document_id != null) {
        const documents = await listDocuments()
        if (currentIdRef.current !== requestedId) return
        setSale(null)
        setReceiptDocument(documents.find((doc) => doc.id === d.receipt_document_id) ?? null)
      } else {
        setSale(null)
        setReceiptDocument(null)
      }
    } catch (err) {
      if (currentIdRef.current === requestedId) {
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить долг')
      }
    } finally {
      if (currentIdRef.current === requestedId) setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debtId])

  if (!loading && !debt) {
    return (
      <div className={layoutStyles.stack}>
        <Link to="/debts" className={layoutStyles.backLink}>
          <IconChevronLeft size={16} stroke={1.8} /> Все долги
        </Link>
        <p className={layoutStyles.error}>{error ?? 'Долг не найден'}</p>
      </div>
    )
  }

  return (
    <div className={layoutStyles.stack}>
      <Link to="/debts" className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> Все долги
      </Link>

      {!debt ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : (
        <DebtCard
          debt={debt}
          clients={clients}
          suppliers={suppliers}
          sale={sale}
          receiptDocument={receiptDocument}
          products={products}
          units={units}
          onReload={load}
        />
      )}
    </div>
  )
}
