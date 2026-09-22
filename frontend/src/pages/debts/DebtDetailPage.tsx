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
  IconReceipt,
} from '@tabler/icons-react'
import { formatMoney } from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from '../../entities/debt/debtStatus'
import { daysOverdue, pluralDays } from '../../entities/debt/dueDate'
import layoutStyles from '../../shared/ui/Layout.module.css'
import detail from '../../shared/ui/DetailPage.module.css'
import styles from './DebtDetailPage.module.css'

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('ru-RU')
}

function nextPaymentDue(debt: Debt): string | null {
  if (debt.is_closed) return null
  if (debt.schedule.length > 0) {
    const sortedRepayments = [...debt.repayments].sort((a, b) => a.on.localeCompare(b.on))
    let paidSoFar = 0
    let repaymentIndex = 0
    for (const s of debt.schedule) {
      const amount = Number(s.amount)
      while (paidSoFar < amount - 0.01 && repaymentIndex < sortedRepayments.length) {
        paidSoFar += Number(sortedRepayments[repaymentIndex].amount)
        repaymentIndex += 1
      }
      const paid = paidSoFar >= amount - 0.01
      if (paid) {
        paidSoFar -= amount
      } else {
        return s.due_date
      }
    }
    return null
  }
  return debt.due_date
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
  const paidPercent =
    debt && Number(debt.amount) > 0
      ? Math.min(100, Math.max(0, (Number(debt.repaid) / Number(debt.amount)) * 100))
      : 0
  const nextDue = debt ? nextPaymentDue(debt) : null
  const progressTone = dueMetricDanger ? 'danger' : dueMetricWarn || debt?.status === 'partially_paid' ? 'warn' : 'ok'
  const iconToneClass =
    debt?.is_closed
      ? styles.heroIconOk
      : dueMetricDanger
        ? styles.heroIconDanger
        : dueMetricWarn
          ? styles.heroIconWarn
          : ''

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
            <div className={styles.heroTopRow}>
              <div className={styles.heroIdentity}>
                <div className={[styles.heroIcon, iconToneClass].filter(Boolean).join(' ')}>
                  <Icon size={26} stroke={1.6} />
                </div>
                <div className={styles.heroText}>
                  <div className={styles.heroTags}>
                    <span className={DEBT_STATUS_BADGE_CLASS[debt.status]}>
                      {DEBT_STATUS_LABELS[debt.status]}
                    </span>
                    <span className={styles.kindChip}>
                      {debt.client_id != null ? 'Нам должны' : 'Мы должны'}
                    </span>
                  </div>
                  <h2 className={styles.heroTitle}>{counterpartyName(debt)}</h2>
                </div>
              </div>
              <div className={styles.heroAmountBlock}>
                <span className={styles.heroAmountLabel}>
                  {debt.is_closed ? 'Погашен' : 'Остаток'}
                </span>
                <div className={styles.heroAmount}>
                  {formatMoney(debt.is_closed ? debt.amount : debt.balance)}
                  <span className={styles.heroAmountCurrency}>₽</span>
                </div>
              </div>
            </div>
            <div className={styles.heroMeta}>
              <span>Выдан {formatDate(debt.issued_at)}</span>
              {debt.due_date && (
                <span className={dueMetricDanger ? layoutStyles.textDanger : dueMetricWarn ? layoutStyles.textWarning : undefined}>
                  {debt.is_closed
                    ? `Срок был до ${formatDate(debt.due_date)}`
                    : overdueDays > 0
                      ? `Просрочен на ${overdueDays} ${pluralDays(overdueDays)}`
                      : overdueDays === 0
                        ? 'Срок сегодня'
                        : `Срок до ${formatDate(debt.due_date)}`}
                </span>
              )}
              {debt.note && !debt.sale_id && !debt.receipt_document_id && (
                <span>{debt.note}</span>
              )}
            </div>
          </section>

          {!debt.is_closed && (
            <section
              className={`${styles.progressCard} ${detail.reveal}`}
              style={{ '--reveal-delay': '40ms' } as CSSProperties}
            >
              <div className={styles.progressHead}>
                <span className={styles.progressPaid}>
                  Оплачено {formatMoney(debt.repaid)} ₽
                  <span className={layoutStyles.textMuted}> из {formatMoney(debt.amount)} ₽</span>
                </span>
                {nextDue && (
                  <span className={styles.progressMeta}>
                    Следующая · {formatDate(nextDue)}
                  </span>
                )}
              </div>
              <div className={styles.progressTrack}>
                <div
                  className={[
                    styles.progressFill,
                    progressTone === 'danger' && styles.progressFillDanger,
                    progressTone === 'warn' && styles.progressFillWarn,
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  style={{ width: `${paidPercent}%` }}
                />
              </div>
            </section>
          )}

          <section
            className={`${detail.metrics} ${detail.reveal}`}
            style={{ '--reveal-delay': '80ms' } as CSSProperties}
          >
            <div className={detail.metric}>
              <span className={detail.metricIcon}>
                <IconCoin size={18} stroke={1.8} />
              </span>
              <div className={detail.metricBody}>
                <strong>
                  {formatMoney(debt.amount)}
                  <span className={detail.metricCurrency}>₽</span>
                </strong>
                <span>Всего</span>
              </div>
            </div>
            <div className={detail.metric}>
              <span className={detail.metricIcon}>
                <IconCash size={18} stroke={1.8} />
              </span>
              <div className={detail.metricBody}>
                <strong>
                  {formatMoney(debt.repaid)}
                  <span className={detail.metricCurrency}>₽</span>
                </strong>
                <span>Погашено</span>
              </div>
            </div>
            <div className={detail.metric}>
              <span
                className={`${detail.metricIcon} ${!debt.is_closed && Number(debt.balance) > 0 ? detail.metricIconWarn : ''}`}
              >
                <IconWallet size={18} stroke={1.8} />
              </span>
              <div className={detail.metricBody}>
                <strong>
                  {formatMoney(debt.balance)}
                  <span className={detail.metricCurrency}>₽</span>
                </strong>
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

          {(debt.sale_id != null || debt.receipt_document_id != null) && (
            <div className={`${styles.section} ${detail.reveal}`} style={{ '--reveal-delay': '100ms' } as CSSProperties}>
              {debt.sale_id != null ? (
                <>
                  <Link to={`/sales/${debt.sale_id}`} className={styles.sourceLink}>
                    <IconReceipt size={15} stroke={1.8} /> Из продажи №{debt.sale_id}
                  </Link>
                  {sale != null && Number(sale.paid_now ?? 0) > 0 && (
                    <p className={layoutStyles.textMuted} style={{ margin: '8px 0 0' }}>
                      Продажа на {formatMoney(sale.total)} ₽ · оплачено сразу{' '}
                      {formatMoney(sale.paid_now ?? 0)} ₽ · в долг{' '}
                      {formatMoney(sale.debt_amount ?? debt.amount)} ₽
                    </p>
                  )}
                </>
              ) : (
                <span className={styles.sourceLink} style={{ color: 'var(--text-muted)', cursor: 'default' }}>
                  <IconReceipt size={15} stroke={1.8} /> Из приёмки №
                  {receiptDocument?.number ?? debt.receipt_document_id}
                </span>
              )}
            </div>
          )}

          <div className={detail.reveal} style={{ '--reveal-delay': '120ms' } as CSSProperties}>
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
              embedded
            />
          </div>
        </>
      )}
    </div>
  )
}
