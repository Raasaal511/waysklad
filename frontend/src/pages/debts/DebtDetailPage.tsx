import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getDebt, type Debt } from '../../entities/debt/api'
import { searchClients, listSuppliers, type Client, type Supplier } from '../../entities/counterparty/api'
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
  const { products, units, ensureProducts, ensureUnits } = useCatalog()

  const [debt, setDebt] = useState<Debt | null>(null)
  const [clients, setClients] = useState<Client[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sale, setSale] = useState<Sale | null>(null)
  const [receiptDocument, setReceiptDocument] = useState<DocumentHistoryEntry | null>(null)

  async function load() {
    setLoading(true)
    try {
      const [d, clientList, supplierList] = await Promise.all([
        getDebt(debtId),
        searchClients('', true),
        listSuppliers(),
        ensureProducts(),
        ensureUnits(),
      ])
      setDebt(d)
      setClients(clientList)
      setSuppliers(supplierList)
      if (d.sale_id != null) {
        const s = await getSale(d.sale_id)
        setSale(s)
        setReceiptDocument(null)
      } else if (d.receipt_document_id != null) {
        const documents = await listDocuments()
        setSale(null)
        setReceiptDocument(documents.find((doc) => doc.id === d.receipt_document_id) ?? null)
      } else {
        setSale(null)
        setReceiptDocument(null)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить долг')
    } finally {
      setLoading(false)
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
