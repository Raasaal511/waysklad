import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getDebt, type Debt } from '../../entities/debt/api'
import { searchClients, listSuppliers, type Client, type Supplier } from '../../entities/counterparty/api'
import { getSale, type Sale } from '../../entities/sale/api'
import { listDocuments, type DocumentHistoryEntry } from '../../entities/inventory/api'
import { listAllProducts, listUnits, type Product, type Unit } from '../../entities/product/api'
import { DebtCard } from '../../entities/debt/DebtCard'
import { ApiError } from '../../shared/api/client'
import { IconChevronLeft } from '@tabler/icons-react'

export function DebtDetailPage() {
  const { id } = useParams<{ id: string }>()
  const debtId = Number(id)

  const [debt, setDebt] = useState<Debt | null>(null)
  const [clients, setClients] = useState<Client[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sale, setSale] = useState<Sale | null>(null)
  const [receiptDocument, setReceiptDocument] = useState<DocumentHistoryEntry | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [units, setUnits] = useState<Unit[]>([])

  async function load() {
    setLoading(true)
    try {
      const [d, clientList, supplierList] = await Promise.all([
        getDebt(debtId),
        searchClients('', true),
        listSuppliers(),
      ])
      setDebt(d)
      setClients(clientList)
      setSuppliers(supplierList)
      if (d.sale_id != null) {
        const [s, productList, unitList] = await Promise.all([getSale(d.sale_id), listAllProducts(), listUnits()])
        setSale(s)
        setReceiptDocument(null)
        setProducts(productList)
        setUnits(unitList)
      } else if (d.receipt_document_id != null) {
        const [documents, productList, unitList] = await Promise.all([
          listDocuments(),
          listAllProducts(),
          listUnits(),
        ])
        setSale(null)
        setReceiptDocument(documents.find((doc) => doc.id === d.receipt_document_id) ?? null)
        setProducts(productList)
        setUnits(unitList)
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
      <div className="stack">
        <Link to="/debts" className="back-link">
          <IconChevronLeft size={16} stroke={1.8} /> Все долги
        </Link>
        <p className="error">{error ?? 'Долг не найден'}</p>
      </div>
    )
  }

  return (
    <div className="stack">
      <Link to="/debts" className="back-link">
        <IconChevronLeft size={16} stroke={1.8} /> Все долги
      </Link>

      {!debt ? (
        <p className="text-muted">Загрузка…</p>
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
