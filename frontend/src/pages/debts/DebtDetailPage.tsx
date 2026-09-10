import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getDebt, type Debt } from '../../entities/debt/api'
import { searchClients, type Client } from '../../entities/counterparty/api'
import { getSale, type Sale } from '../../entities/sale/api'
import { listDocuments, type DocumentHistoryEntry } from '../../entities/inventory/api'
import { DebtCard } from '../../entities/debt/DebtCard'
import { ApiError } from '../../shared/api/client'
import { useCatalog } from '../../app/CatalogContext'
import {
  IconChevronLeft,
  IconUser,
  IconTruck,
  IconCoin,
  IconCash,
  IconWallet,
  IconCalendarDue,
} from '@tabler/icons-react'
import { formatMoney } from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from '../../entities/debt/debtStatus'
import { daysOverdue, pluralDays } from '../../entities/debt/dueDate'
import layoutStyles from '../../shared/ui/Layout.module.css'
import detail from '../products/ProductDetailPage.module.css'
import styles from './DebtDetailPage.module.css'

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('ru-RU')
}

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

  const counterpartyName = (d: Debt) =>
    d.client_id
      ? clients.find((c) => c.id === d.client_id)?.name ?? `Клиент #${d.client_id}`
      : suppliers.find((s) => s.id === d.supplier_id)?.name ?? `Поставщик #${d.supplier_id}`

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

  const Icon = debt?.client_id != null ? IconUser : IconTruck
  const overdueDays = debt?.due_date && !debt.is_closed ? daysOverdue(debt.due_date) : 0
  const dueMetricDanger = overdueDays > 0
  const dueMetricWarn = overdueDays === 0 && debt?.due_date != null && !debt.is_closed

  return (
    <div className={layoutStyles.stack}>
      <Link to="/debts" className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> Все долги
      </Link>

      {!debt ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : (
        <>
          <section
            className={`${styles.hero} ${detail.reveal}`}
            style={{ '--reveal-delay': '0ms' } as CSSProperties}
          >
            <div className={styles.heroIcon}>
              <Icon size={28} stroke={1.6} />
            </div>
            <div className={detail.heroBody}>
              <div className={detail.heroTop}>
                <div className={detail.heroHeading}>
                  <div className={detail.heroTags}>
                    <span className={DEBT_STATUS_BADGE_CLASS[debt.status]}>
                      {DEBT_STATUS_LABELS[debt.status]}
                    </span>
                    <span className={styles.kindChip}>
                      {debt.client_id != null ? 'Нам должны' : 'Мы должны'}
                    </span>
                  </div>
                  <h2 className={detail.heroTitle}>{counterpartyName(debt)}</h2>
                </div>
              </div>
              <div className={detail.heroPrice}>
                {debt.is_closed ? (
                  <>Погашен · {formatMoney(debt.amount)} ₽</>
                ) : (
                  <>{formatMoney(debt.balance)} ₽</>
                )}
              </div>
              <div className={detail.heroMeta}>
                <span>Выдан {formatDate(debt.issued_at)}</span>
                {debt.due_date && (
                  <span className={dueMetricDanger ? layoutStyles.textDanger : undefined}>
                    {debt.is_closed
                      ? `Срок был до ${formatDate(debt.due_date)}`
                      : overdueDays > 0
                        ? `Просрочен на ${overdueDays} ${pluralDays(overdueDays)}`
                        : overdueDays === 0
                          ? 'Срок сегодня'
                          : `Срок до ${formatDate(debt.due_date)}`}
                  </span>
                )}
              </div>
            </div>
          </section>

          <section
            className={`${detail.metrics} ${detail.reveal}`}
            style={{ '--reveal-delay': '60ms' } as CSSProperties}
          >
            <div className={detail.metric}>
              <span className={detail.metricIcon}>
                <IconCoin size={18} stroke={1.8} />
              </span>
              <div className={detail.metricBody}>
                <strong>{formatMoney(debt.amount)} ₽</strong>
                <span>Всего</span>
              </div>
            </div>
            <div className={detail.metric}>
              <span className={detail.metricIcon}>
                <IconCash size={18} stroke={1.8} />
              </span>
              <div className={detail.metricBody}>
                <strong>{formatMoney(debt.repaid)} ₽</strong>
                <span>Погашено</span>
              </div>
            </div>
            <div className={detail.metric}>
              <span className={`${detail.metricIcon} ${!debt.is_closed && Number(debt.balance) > 0 ? detail.metricIconWarn : ''}`}>
                <IconWallet size={18} stroke={1.8} />
              </span>
              <div className={detail.metricBody}>
                <strong>{formatMoney(debt.balance)} ₽</strong>
                <span>Остаток</span>
              </div>
            </div>
            <div className={detail.metric}>
              <span
                className={`${detail.metricIcon} ${dueMetricDanger ? detail.metricIconDanger : dueMetricWarn ? detail.metricIconWarn : ''}`}
              >
                <IconCalendarDue size={18} stroke={1.8} />
              </span>
              <div className={detail.metricBody}>
                <strong>
                  {debt.due_date
                    ? debt.is_closed
                      ? formatDate(debt.due_date)
                      : overdueDays > 0
                        ? `+${overdueDays} дн.`
                        : formatDate(debt.due_date)
                    : '—'}
                </strong>
                <span>
                  {debt.due_date && !debt.is_closed && overdueDays > 0
                    ? 'Просрочка'
                    : debt.due_date && !debt.is_closed && overdueDays === 0
                      ? 'Срок сегодня'
                      : 'Срок'}
                </span>
              </div>
            </div>
          </section>

          <div className={detail.reveal} style={{ '--reveal-delay': '110ms' } as CSSProperties}>
            <DebtCard
              debt={debt}
              clients={clients}
              suppliers={suppliers}
              sale={sale}
              receiptDocument={receiptDocument}
              products={products}
              units={units}
              onReload={load}
              showHeader={false}
            />
          </div>
        </>
      )}
    </div>
  )
}
