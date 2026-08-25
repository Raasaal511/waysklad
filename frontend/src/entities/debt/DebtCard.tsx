import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { repayDebt, extendDebt, createInstallment, getDebtHistory, type Debt, type DebtHistoryEntry } from './api'
import type { Client, Supplier } from '../counterparty/api'
import type { Sale } from '../sale/api'
import type { DocumentHistoryEntry } from '../inventory/api'
import type { Product, Unit } from '../product/api'
import {
  type InstallmentPeriod,
  INSTALLMENT_PERIOD_OPTIONS,
  buildInstallmentSchedule,
} from './installmentSchedule'
import { ApiError } from '../../shared/api/client'
import layoutStyles from '../../shared/ui/Layout.module.css'
import { Modal } from '../../shared/ui/Modal'
import {
  IconUser,
  IconTruck,
  IconReceipt,
  IconCheck,
  IconCalendarDue,
  IconCash,
  IconCalendarTime,
  IconCalendarRepeat,
  IconClockExclamation,
  IconCalendarPlus,
  IconCalendarRepeat as IconInstallment,
  type Icon as TablerIcon,
} from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
import { InfoHint } from '../../shared/ui/InfoHint'
import { HistoryDisclosure } from '../../shared/ui/HistoryDisclosure'
import { formatMoney, formatQuantity, normalizeDecimalInput } from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from './debtStatus'
import { daysOverdue, pluralDays } from './dueDate'
import styles from './DebtCard.module.css'

const DEBT_HISTORY_ACTION_LABELS: Record<string, string> = {
  'debt.issue': 'Долг выдан клиенту',
  'debt.issue_supplier': 'Долг выдан поставщику',
  'debt.repay': 'Внесена оплата',
  'debt.extend': 'Продлён срок',
  'debt.installment': 'Составлен график рассрочки',
}

const DEBT_HISTORY_ACTION_ICONS: Record<string, TablerIcon> = {
  'debt.issue': IconUser,
  'debt.issue_supplier': IconTruck,
  'debt.repay': IconCash,
  'debt.extend': IconCalendarPlus,
  'debt.installment': IconInstallment,
}

function formatDebtHistoryDetail(entry: DebtHistoryEntry): string | null {
  const d = entry.details
  switch (entry.action) {
    case 'debt.issue':
    case 'debt.issue_supplier':
      return d.amount != null ? `${formatMoney(String(d.amount))} ₽` : null
    case 'debt.repay':
      return d.amount != null
        ? `Внесено ${formatMoney(String(d.amount))} ₽ · остаток ${formatMoney(String(d.balance ?? '0'))} ₽`
        : null
    case 'debt.extend':
      return d.new_due_date ? `Новый срок ${formatDate(String(d.new_due_date))}` : null
    case 'debt.installment':
      return d.payments != null ? `Платежей: ${d.payments}` : null
    default:
      return null
  }
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('ru-RU')
}

function formatPayDate(value: string) {
  return new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function pluralItems(n: number): string {
  const abs = Math.abs(n) % 100
  const last = abs % 10
  if (abs > 10 && abs < 20) return 'товаров'
  if (last === 1) return 'товар'
  if (last >= 2 && last <= 4) return 'товара'
  return 'товаров'
}

function pluralPayments(n: number): string {
  const abs = Math.abs(n) % 100
  const last = abs % 10
  if (abs > 10 && abs < 20) return 'оплат'
  if (last === 1) return 'оплата'
  if (last >= 2 && last <= 4) return 'оплаты'
  return 'оплат'
}

// Дата следующего платежа: для рассрочки — due_date первой ещё не покрытой
// оплатами строки графика (та же эвристика, что и в InstallmentSchedule),
// для обычного долга — просто общий срок, если он задан и долг не закрыт.
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

function DueDateLabel({ dueDate, prefix = 'срок до' }: { dueDate: string; prefix?: string }) {
  const overdue = daysOverdue(dueDate)
  if (overdue > 0) {
    return (
      <span className={layoutStyles.textDanger}>
        просрочен на {overdue} {pluralDays(overdue)}
      </span>
    )
  }
  if (overdue === 0) {
    return <span className={layoutStyles.textWarning}>срок сегодня</span>
  }
  return (
    <span>
      {prefix} {formatDate(dueDate)}
    </span>
  )
}

// Прогресс оплаты как единая залитая полоса (доля filled/segments) —
// не ряд отдельных "капсул" с зазорами (превращалось в кашу при 100%
// заполнении). showSegments рисует маленькие точки-стыки между сегментами
// поверх полосы, когда segments несёт смысл (число платежей рассрочки) —
// так видно и общий процент, и сколько именно частей оплачено. dueDate
// рисует финальную точку-цель (срок выплаты, покрупнее) в конце полосы.
function DottedProgress({
  segments,
  filled,
  dueDate,
  showSegments = false,
}: {
  segments: number
  filled: number
  dueDate?: string | null
  showSegments?: boolean
}) {
  const percent = segments > 0 ? Math.min(100, Math.max(0, (filled / segments) * 100)) : 0
  const segmentWidth = segments > 0 ? 100 / segments : 0
  return (
    <div className={styles['debt-pay-progress-dots']}>
      <div className={styles['debt-pay-progress-track']}>
        <div className={styles['debt-pay-progress-fill']} style={{ width: `${percent}%` }} />
        {showSegments &&
          segments > 1 &&
          Array.from({ length: segments - 1 }, (_, i) => (
            <span
              key={i}
              className={[styles['debt-pay-progress-tick'], i < filled && styles['debt-pay-progress-tick-filled']]
                .filter(Boolean)
                .join(' ')}
              style={{ left: `${segmentWidth * (i + 1)}%` }}
            />
          ))}
      </div>
      <span
        className={[styles['debt-pay-progress-goal'], filled >= segments && styles['debt-pay-progress-goal-reached']]
          .filter(Boolean)
          .join(' ')}
        title={dueDate ? `Срок ${formatDate(dueDate)}` : 'Полное погашение'}
      >
        {filled >= segments && <IconCheck size={8} stroke={3} />}
      </span>
    </div>
  )
}

export function DebtCard({
  debt,
  clients,
  suppliers,
  sale,
  receiptDocument,
  products,
  units,
  onReload,
  showHeader = true,
}: {
  debt: Debt
  clients: Client[]
  suppliers: Supplier[]
  sale: Sale | null
  receiptDocument: DocumentHistoryEntry | null
  products: Product[]
  units: Unit[]
  onReload: () => void
  showHeader?: boolean
}) {
  const [showRepay, setShowRepay] = useState(false)
  const [showExtend, setShowExtend] = useState(false)
  const [showInstallment, setShowInstallment] = useState(false)

  const counterpartyName = (d: Debt) =>
    d.client_id
      ? clients.find((c) => c.id === d.client_id)?.name ?? `Клиент #${d.client_id}`
      : suppliers.find((s) => s.id === d.supplier_id)?.name ?? `Поставщик #${d.supplier_id}`

  const unitName = (productId: number) => {
    const code = products.find((p) => p.id === productId)?.unit_code
    return units.find((u) => u.code === code)?.name ?? ''
  }

  const Icon = debt.client_id != null ? IconUser : IconTruck

  return (
    <div className={layoutStyles.stack}>
      {showHeader && (
        <div className={layoutStyles.sectionTitle}>
          <div className={layoutStyles.stack} style={{ gap: 2 }}>
            <div className={layoutStyles.row} style={{ gap: 8, alignItems: 'center' }}>
              <span className={styles['debt-group-icon']}>
                <Icon size={18} stroke={1.8} />
              </span>
              <h2>{counterpartyName(debt)}</h2>
              <span className={DEBT_STATUS_BADGE_CLASS[debt.status]}>{DEBT_STATUS_LABELS[debt.status]}</span>
            </div>
            <span className={layoutStyles.textMuted}>
              {debt.client_id != null ? 'Должен нам' : 'Мы должны'} · выдан {formatDate(debt.issued_at)}
              {debt.due_date && !debt.is_closed && (
                <>
                  {' · '}
                  <DueDateLabel dueDate={debt.due_date} />
                </>
              )}
              {debt.due_date && debt.is_closed && ` · срок был до ${formatDate(debt.due_date)}`}
            </span>
          </div>
        </div>
      )}

      <div className={styles['debt-pay-progress']}>
        <span className={styles['debt-pay-progress-paid']}>Оплачено {formatMoney(debt.repaid)} ₽</span>
        {!debt.is_closed && (
          <div className={styles['debt-pay-progress-labels']}>
            <span className={styles['debt-pay-progress-balance']}>
              Остаток {formatMoney(debt.balance)} ₽{' '}
              <span className={layoutStyles.textMuted}>из {formatMoney(debt.amount)} ₽</span>
            </span>
            {nextPaymentDue(debt) && (
              <span className={[styles['debt-pay-progress-next'], layoutStyles.textMuted].join(' ')}>
                Следующая оплата · {formatDate(nextPaymentDue(debt)!)}
              </span>
            )}
          </div>
        )}
      </div>

      <span className={styles['debt-item-source']}>
        {debt.sale_id != null ? (
          <Link to={`/?openSale=${debt.sale_id}`} className={styles['debt-item-source-link']}>
            <IconReceipt size={13} stroke={1.8} /> Из продажи №{debt.sale_id}
          </Link>
        ) : debt.receipt_document_id != null ? (
          <span className={layoutStyles.textMuted}>
            <IconReceipt size={13} stroke={1.8} /> Из приёмки №
            {receiptDocument?.number ?? debt.receipt_document_id}
          </span>
        ) : debt.note ? (
          <span className={layoutStyles.textMuted}>{debt.note}</span>
        ) : (
          <span className={layoutStyles.textMuted}>Выдан вручную</span>
        )}
      </span>

      {sale && sale.lines.length > 0 && (
        <div className={[layoutStyles.card, layoutStyles.cardFull, layoutStyles.stack].join(' ')}>
          <div className={styles['debt-receipt-header']}>
            <h3>Товары из продажи</h3>
            <span className={styles['debt-receipt-count']}>
              {sale.lines.length} {pluralItems(sale.lines.length)}
            </span>
          </div>
          <div className={styles['debt-receipt']}>
            {sale.lines.map((line) => (
              <div key={line.id} className={styles['debt-receipt-row']}>
                <span className={styles['debt-receipt-name']}>
                  {products.find((p) => p.id === line.product_id)?.name ?? `Товар #${line.product_id}`}
                </span>
                <span className={styles['debt-receipt-qty']}>
                  × {formatQuantity(line.quantity)} {unitName(line.product_id)}
                </span>
                <span className={styles['debt-receipt-leader']} />
                <span className={styles['debt-receipt-sum']}>{formatMoney(line.total)} ₽</span>
              </div>
            ))}
          </div>
          <div className={styles['debt-receipt-total']}>
            <span>Итого</span>
            <strong>{formatMoney(String(sale.lines.reduce((sum, l) => sum + Number(l.total), 0)))} ₽</strong>
          </div>
        </div>
      )}

      {receiptDocument && receiptDocument.lines.length > 0 && (
        <div className={[layoutStyles.card, layoutStyles.cardFull, layoutStyles.stack].join(' ')}>
          <div className={styles['debt-receipt-header']}>
            <h3>Товары из приёмки</h3>
            <span className={styles['debt-receipt-count']}>
              {receiptDocument.lines.length} {pluralItems(receiptDocument.lines.length)}
            </span>
          </div>
          <div className={styles['debt-receipt']}>
            {receiptDocument.lines.map((line, i) => (
              <div key={i} className={styles['debt-receipt-row']}>
                <span className={styles['debt-receipt-name']}>
                  {products.find((p) => p.id === line.product_id)?.name ?? `Товар #${line.product_id}`}
                </span>
                <span className={styles['debt-receipt-qty']}>
                  × {formatQuantity(line.quantity)} {unitName(line.product_id)}
                </span>
                <span className={styles['debt-receipt-leader']} />
                <span className={styles['debt-receipt-sum']}>
                  {line.cost != null ? `${formatMoney(String(Number(line.cost) * Number(line.quantity)))} ₽` : '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!debt.is_closed && (
        <div className={styles['debt-detail-actions']}>
          {debt.schedule.length === 0 && (
            <Button variant="secondary" onClick={() => setShowRepay(true)}>
              <IconCash size={15} stroke={1.8} /> Внести оплату
            </Button>
          )}
          <Button variant="secondary" onClick={() => setShowExtend(true)}>
            <IconCalendarTime size={15} stroke={1.8} /> Продлить срок
          </Button>
          <Button variant="secondary" onClick={() => setShowInstallment(true)}>
            <IconCalendarRepeat size={15} stroke={1.8} />{' '}
            {debt.schedule.length === 0 ? 'Рассрочка' : 'Пересобрать график'}
          </Button>
        </div>
      )}

      {showRepay && (
        <Modal title="Внести оплату" onClose={() => setShowRepay(false)}>
          <RepayDebtForm
            debtId={debt.id}
            balance={debt.balance}
            onDone={() => {
              setShowRepay(false)
              onReload()
            }}
          />
        </Modal>
      )}

      {showExtend && (
        <Modal
          title={
            debt.due_date ? (
              <>
                Продлить срок
                <span className={styles['modal-title-sub']}>сейчас до {formatDate(debt.due_date)}</span>
              </>
            ) : (
              'Продлить срок'
            )
          }
          onClose={() => setShowExtend(false)}
        >
          <ExtendDebtForm
            debtId={debt.id}
            currentDueDate={debt.due_date}
            balance={debt.balance}
            hasSchedule={debt.schedule.length > 0}
            onDone={() => {
              setShowExtend(false)
              onReload()
            }}
          />
        </Modal>
      )}

      {showInstallment && (
        <Modal
          title={debt.schedule.length === 0 ? 'Рассрочка' : 'Пересобрать график'}
          onClose={() => setShowInstallment(false)}
        >
          <InstallmentForm
            debtId={debt.id}
            balance={debt.balance}
            onDone={() => {
              setShowInstallment(false)
              onReload()
            }}
          />
        </Modal>
      )}

      {debt.schedule.length > 0 && (
        <div className={[layoutStyles.card, layoutStyles.cardFull, layoutStyles.stack].join(' ')}>
          <h3>График рассрочки</h3>
          <InstallmentSchedule debt={debt} onDone={onReload} />
        </div>
      )}

      {debt.schedule.length === 0 && debt.repayments.length > 0 && (
        <div className={[layoutStyles.card, layoutStyles.cardFull, layoutStyles.stack].join(' ')}>
          <div className={styles['debt-payments-header']}>
            <span className={layoutStyles.row} style={{ gap: 8 }}>
              <h3>Оплаты</h3>
              <span className={layoutStyles.textMuted}>
                {debt.repayments.length} {pluralPayments(debt.repayments.length)}
              </span>
            </span>
            <span className={styles['debt-payments-total']}>
              {formatMoney(String(debt.repayments.reduce((sum, r) => sum + Number(r.amount), 0)))} ₽
            </span>
          </div>
          <div className={styles['debt-payments-list']}>
            {[...debt.repayments]
              .sort((a, b) => b.on.localeCompare(a.on))
              .map((r, i) => (
                <div key={i} className={styles['debt-payment-row']}>
                  <span className={styles['debt-payment-check']}>
                    <IconCheck size={12} stroke={2.5} />
                  </span>
                  <div className={styles['debt-payment-main']}>
                    <span className={styles['debt-payment-date']}>{formatPayDate(r.on)}</span>
                    {r.note && <span className={styles['debt-payment-note']}>{r.note}</span>}
                  </div>
                  <strong className={styles['debt-payment-amount']}>{formatMoney(r.amount)} ₽</strong>
                </div>
              ))}
          </div>
        </div>
      )}

      <HistoryDisclosure
        load={() => getDebtHistory(debt.id)}
        actionLabels={DEBT_HISTORY_ACTION_LABELS}
        actionIcons={DEBT_HISTORY_ACTION_ICONS}
        formatDetail={formatDebtHistoryDetail}
      />
    </div>
  )
}

function RepayDebtForm({
  debtId,
  balance,
  onDone,
}: {
  debtId: number
  balance: string
  onDone: () => void
}) {
  const [amount, setAmount] = useState('')
  const [paidOn, setPaidOn] = useState(new Date().toISOString().slice(0, 10))
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const willClose = amount !== '' && Number(amount) >= Number(balance) - 0.01

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!amount) return
    setError(null)
    setSaving(true)
    try {
      await repayDebt(debtId, { amount, paid_on: paidOn, note })
      setAmount('')
      setNote('')
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось внести оплату')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={[layoutStyles.form, styles['debt-detail-form']].join(' ')} onSubmit={handleSubmit}>
      <div className={styles['debt-form-balance']}>
        <span>Остаток долга</span>
        <strong>{formatMoney(balance)} ₽</strong>
      </div>
      <p className={styles['debt-form-explainer']}>
        Разовый платёж без графика — просто уменьшает долг на внесённую сумму.
      </p>
      <label className={layoutStyles.field}>
        Сумма
        <input
          type="text"
          inputMode="decimal"
          placeholder="Сколько внесли"
          value={amount}
          onChange={(e) => {
            const normalized = normalizeDecimalInput(e.target.value)
            if (normalized !== null) setAmount(normalized)
          }}
          required
        />
      </label>
      <label className={layoutStyles.field}>
        Дата оплаты
        <DateInput value={paidOn} onChange={setPaidOn} max={new Date().toISOString().slice(0, 10)} />
        <span className={layoutStyles.fieldHint}>Если оплату уже получили раньше — укажите тот день, а не сегодня</span>
      </label>
      <label className={layoutStyles.field}>
        Комментарий
        <input placeholder="Необязательно" value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      {willClose && (
        <p className={styles['debt-close-hint']}>Этой суммой долг будет погашен полностью — статус станет «Погашен».</p>
      )}
      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button type="submit" disabled={saving || !amount}>
        {saving ? 'Сохранение…' : willClose ? 'Погасить долг' : 'Сохранить'}
      </Button>
    </form>
  )
}

function InstallmentSchedule({ debt, onDone }: { debt: Debt; onDone: () => void }) {
  const [savingIndex, setSavingIndex] = useState<number | null>(null)
  const [payingIndex, setPayingIndex] = useState<number | null>(null)
  const [payAmount, setPayAmount] = useState('')
  const [payDate, setPayDate] = useState('')
  const [postponingIndex, setPostponingIndex] = useState<number | null>(null)
  const [postponeDate, setPostponeDate] = useState('')
  const [error, setError] = useState<string | null>(null)

  // Сколько реально внесено ПО ТЕКУЩЕМУ графику — не сумма всех repayments
  // за всю историю долга (график мог пересобираться, и старые оплаты уже
  // учтены в том, что новый график меньше исходной суммы), а разница между
  // суммой строк графика и текущим остатком долга. Иначе при пересборке
  // старые оплаты засчитывались бы графику второй раз (баг: "оплачено 6 из
  // 6", хотя реально погашена только часть).
  const totalScheduleAmount = debt.schedule.reduce((sum, s) => sum + Number(s.amount), 0)
  let appliedToSchedule = Math.max(0, totalScheduleAmount - Number(debt.balance))

  // Дата "фактической выплаты" по строке — лучшее приближение прогоном
  // истории оплат по порядку дат; сам факт "оплачена ли строка" при этом
  // определяется НЕ этим прогоном (см. appliedToSchedule выше), а только
  // используется, чтобы подобрать правдоподобную дату для отображения.
  // lastRepaymentOn хранит дату последнего просмотренного платежа отдельно
  // от цикла while — один платёж может покрывать сразу несколько строк
  // графика (буфер paidSoFarForDates больше суммы текущей строки), и тогда
  // while на этой итерации не выполнится ни разу, но дата уже известна.
  const sortedRepayments = [...debt.repayments].sort((a, b) => a.on.localeCompare(b.on))
  let paidSoFarForDates = 0
  let repaymentIndex = 0
  let lastRepaymentOn: string | null = null
  const rows = debt.schedule.map((s) => {
    const amount = Number(s.amount)
    while (paidSoFarForDates < amount - 0.01 && repaymentIndex < sortedRepayments.length) {
      paidSoFarForDates += Number(sortedRepayments[repaymentIndex].amount)
      lastRepaymentOn = sortedRepayments[repaymentIndex].on
      repaymentIndex += 1
    }
    const paidOn = paidSoFarForDates >= amount - 0.01 ? lastRepaymentOn : null
    if (paidSoFarForDates >= amount - 0.01) paidSoFarForDates -= amount
    const paid = appliedToSchedule >= amount - 0.01
    // Остаток именно по этой строке — с учётом переплаты, которая уже
    // "перетекла" сюда с предыдущих платежей (появляется только у первой
    // неоплаченной строки: appliedToSchedule ещё не обнулился прошлыми
    // строками, но самой строки целиком не хватило, чтобы закрыть её).
    const remaining = paid ? 0 : Math.round(Math.max(0, amount - appliedToSchedule) * 100) / 100
    if (paid) appliedToSchedule -= amount
    return { ...s, paid, paidOn: paid ? paidOn : null, remaining }
  })
  const paidCount = rows.filter((r) => r.paid).length
  const nextUnpaidIndex = rows.findIndex((r) => !r.paid)

  async function markPaid(index: number) {
    if (!payAmount || !payDate) return
    setError(null)
    setSavingIndex(index)
    try {
      await repayDebt(debt.id, { amount: payAmount, paid_on: payDate })
      setPayingIndex(null)
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось отметить оплату')
    } finally {
      setSavingIndex(null)
    }
  }

  async function postpone(index: number) {
    if (!postponeDate) return
    setError(null)
    setSavingIndex(index)
    try {
      // createInstallment полностью заменяет график и требует, чтобы сумма
      // совпадала с ТЕКУЩИМ остатком долга — уже оплаченные (по эвристике)
      // строки в новый график не включаем, иначе сумма разъедется вдвое.
      const newSchedule = rows
        .map((r, i) => ({ ...r, due_date: i === index ? postponeDate : r.due_date }))
        .filter((r) => !r.paid)
        .map((r) => ({ due_date: r.due_date, amount: r.amount }))
      await createInstallment(debt.id, newSchedule)
      setPostponingIndex(null)
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось перенести платёж')
    } finally {
      setSavingIndex(null)
    }
  }

  const debtWillClose = (index: number) => {
    if (!payAmount) return false
    // Для текущей строки берём именно то, что реально осталось доплатить
    // (с учётом перетёкшей переплаты), а не номинальную сумму по графику.
    const remainingAfterThis =
      rows[index].remaining + rows.slice(index + 1).reduce((sum, r) => sum + Number(r.amount), 0)
    return Number(payAmount) >= remainingAfterThis - 0.01
  }

  return (
    <div className={layoutStyles.stack}>
      <div className={styles['debt-pay-progress']}>
        <DottedProgress
          segments={rows.length}
          filled={paidCount}
          dueDate={rows[rows.length - 1]?.due_date}
          showSegments
        />
        <div className={styles['debt-pay-progress-labels']}>
          <span className={styles['debt-pay-progress-paid']}>Оплачено {paidCount} из {rows.length}</span>
        </div>
      </div>

      <div className={styles['debt-installment-list']}>
        {rows.map((s, i) => (
          <div
            key={i}
            className={[
              styles['debt-installment-row'],
              s.paid
                ? styles['debt-installment-row-paid']
                : !s.paid && daysOverdue(s.due_date) > 0 && styles['debt-installment-row-overdue'],
            ]
              .filter(Boolean)
              .join(' ')}
          >
            <div className={styles['debt-installment-cols']}>
              <span className={styles['debt-installment-check']}>
                {s.paid ? (
                  <IconCheck size={12} stroke={2.5} />
                ) : daysOverdue(s.due_date) > 0 ? (
                  <IconClockExclamation size={12} stroke={2} />
                ) : (
                  <span className={styles['debt-installment-check-dot']} />
                )}
              </span>
              <span className={styles['debt-installment-main']}>
                <span className={styles['debt-installment-date']}>
                  {formatDate(s.due_date)}
                  {!s.paid && i === nextUnpaidIndex && (
                    <span className={[layoutStyles.badge, layoutStyles.accent].join(' ')}>Следующий</span>
                  )}
                  {!s.paid && daysOverdue(s.due_date) > 0 && (
                    <span className={layoutStyles.textDanger}>
                      просрочен на {daysOverdue(s.due_date)} {pluralDays(daysOverdue(s.due_date))}
                    </span>
                  )}
                </span>
                {s.paidOn && (
                  <span
                    className={
                      s.paidOn !== s.due_date ? styles['debt-installment-paid-on-diff'] : layoutStyles.textMuted
                    }
                  >
                    Оплачен {formatDate(s.paidOn)}
                    {s.paidOn !== s.due_date &&
                      (s.paidOn < s.due_date ? ' · раньше срока' : ' · позже срока')}
                  </span>
                )}
              </span>
              <strong className={styles['debt-installment-sum']}>
                {!s.paid && s.remaining < Number(s.amount) - 0.01 && (
                  <span className={styles['debt-installment-sum-original']}>{formatMoney(s.amount)} ₽</span>
                )}
                {formatMoney(String(s.paid ? s.amount : s.remaining))} ₽
              </strong>
            </div>
            {!s.paid && payingIndex === i && (
              <div className={styles['debt-installment-pay-form']}>
                <label className={layoutStyles.field}>
                  Сумма
                  <input
                    type="text"
                    inputMode="decimal"
                    value={payAmount}
                    onChange={(e) => {
                      const normalized = normalizeDecimalInput(e.target.value)
                      if (normalized !== null) setPayAmount(normalized)
                    }}
                  />
                </label>
                <label className={layoutStyles.field}>
                  Дата оплаты
                  <DateInput value={payDate} onChange={setPayDate} max={new Date().toISOString().slice(0, 10)} />
                </label>
                {debtWillClose(i) ? (
                  <p className={[styles['debt-close-hint'], styles['debt-installment-close-hint']].join(' ')}>
                    Этой суммой долг будет погашен полностью — статус станет «Погашен».
                  </p>
                ) : (
                  payAmount &&
                  Math.abs(Number(payAmount) - s.remaining) > 0.01 && (
                    <p className={[styles['debt-close-hint'], styles['debt-installment-close-hint']].join(' ')}>
                      {Number(payAmount) > s.remaining
                        ? `Платёж больше на ${formatMoney(String(Number(payAmount) - s.remaining))} ₽ — излишек пойдёт в счёт следующих платежей.`
                        : `Платёж меньше на ${formatMoney(String(s.remaining - Number(payAmount)))} ₽ — нехватка перейдёт на следующий платёж.`}
                    </p>
                  )
                )}
                {error && <p className={layoutStyles.error}>{error}</p>}
                <div className={styles['debt-installment-row-actions']}>
                  <Button onClick={() => markPaid(i)} disabled={!payAmount || !payDate || savingIndex === i}>
                    {savingIndex === i ? 'Сохранение…' : 'Подтвердить'}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setPayingIndex(null)
                      setError(null)
                    }}
                  >
                    Отмена
                  </Button>
                </div>
              </div>
            )}
            {!s.paid && payingIndex !== i && (
              <div className={styles['debt-installment-row-actions']}>
                <Button
                  variant="secondary"
                  onClick={() => {
                    setPayingIndex(i)
                    setPayAmount(String(s.remaining))
                    setPayDate(new Date().toISOString().slice(0, 10))
                  }}
                >
                  <IconCheck size={14} stroke={2} /> Оплачено
                </Button>
                {postponingIndex === i ? (
                  <>
                    <DateInput
                      value={postponeDate}
                      onChange={setPostponeDate}
                      min={new Date().toISOString().slice(0, 10)}
                    />
                    <Button onClick={() => postpone(i)} disabled={!postponeDate || savingIndex === i}>
                      Сохранить
                    </Button>
                    <Button variant="secondary" onClick={() => setPostponingIndex(null)}>
                      Отмена
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setPostponingIndex(i)
                      setPostponeDate(s.due_date)
                    }}
                  >
                    <IconCalendarDue size={14} stroke={1.8} /> Перенести
                  </Button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function ExtendDebtForm({
  debtId,
  currentDueDate,
  balance,
  hasSchedule,
  onDone,
}: {
  debtId: number
  currentDueDate: string | null
  balance: string
  hasSchedule: boolean
  onDone: () => void
}) {
  const [newDueDate, setNewDueDate] = useState(currentDueDate ?? '')
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!newDueDate) return
    setError(null)
    setSaving(true)
    try {
      await extendDebt(debtId, { new_due_date: newDueDate, reason })
      setReason('')
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось продлить долг')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={[layoutStyles.form, styles['debt-detail-form']].join(' ')} onSubmit={handleSubmit}>
      <p className={[layoutStyles.textMuted, styles['debt-form-hint-row']].join(' ')}>
        Текущий остаток долга: {formatMoney(balance)} ₽
        <InfoHint text="Переносит общий срок «Долг до» на другую дату." />
      </p>
      {hasSchedule && (
        <p className={styles['debt-extend-warning']}>
          У долга есть график рассрочки — продление меняет только общий срок «Долг до», сроки
          отдельных платежей графика останутся прежними. Перенести конкретный платёж можно
          в самом графике.
        </p>
      )}
      <label className={layoutStyles.field}>
        Новый срок «Долг до»
        <DateInput
          value={newDueDate}
          onChange={setNewDueDate}
          min={new Date().toISOString().slice(0, 10)}
          required
        />
      </label>
      <label className={layoutStyles.field}>
        Причина
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Например: попросил ещё неделю"
        />
      </label>
      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Продлить'}
      </Button>
    </form>
  )
}

function InstallmentForm({
  debtId,
  balance,
  onDone,
}: {
  debtId: number
  balance: string
  onDone: () => void
}) {
  const [downPayment, setDownPayment] = useState('')
  const [parts, setParts] = useState(3)
  const [firstDate, setFirstDate] = useState(new Date().toISOString().slice(0, 10))
  const [period, setPeriod] = useState<InstallmentPeriod>('month')
  const [rows, setRows] = useState<{ due_date: string; amount: string }[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const downPaymentNum = Number(downPayment || '0')
  const downPaymentInvalid = downPaymentNum < 0 || downPaymentNum >= Number(balance)
  const remainingBalance = Math.max(Number(balance) - downPaymentNum, 0).toFixed(2)

  function handlePreview() {
    if (!firstDate) {
      setError('Укажите дату первого платежа')
      return
    }
    if (downPaymentInvalid) {
      setError('Первый взнос должен быть меньше остатка долга')
      return
    }
    setError(null)
    setRows(buildInstallmentSchedule(remainingBalance, parts, firstDate, period))
  }

  const rowsTotal = rows?.reduce((sum, r) => sum + Number(r.amount || '0'), 0) ?? 0
  const balanceMismatch =
    rows != null && Math.round(rowsTotal * 100) !== Math.round(Number(remainingBalance) * 100)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!rows) return
    setError(null)
    setSaving(true)
    try {
      if (downPaymentNum > 0) {
        await repayDebt(debtId, { amount: downPayment, paid_on: firstDate, note: 'Первый взнос' })
      }
      await createInstallment(debtId, rows)
      setRows(null)
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось составить график')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={[layoutStyles.form, styles['debt-detail-form']].join(' ')} onSubmit={handleSubmit}>
      <p className={[layoutStyles.textMuted, styles['debt-form-hint-row']].join(' ')}>
        Остаток к разбивке: {formatMoney(balance)} ₽
        <InfoHint text="Разбивает остаток на платежи по датам — чтобы видеть график и не забыть сроки." />
      </p>
      <label className={layoutStyles.field}>
        Первый взнос (необязательно)
        <input
          type="text"
          inputMode="decimal"
          placeholder="0"
          value={downPayment}
          onChange={(e) => {
            const normalized = normalizeDecimalInput(e.target.value)
            if (normalized === null) return
            setDownPayment(normalized)
            setRows(null)
          }}
        />
      </label>
      {downPaymentNum > 0 && (
        <p className={downPaymentInvalid ? layoutStyles.error : layoutStyles.textMuted}>
          {downPaymentInvalid
            ? 'Первый взнос должен быть меньше остатка долга'
            : `В рассрочку пойдёт ${formatMoney(remainingBalance)} ₽`}
        </p>
      )}
      <div className={layoutStyles.row}>
        <label className={layoutStyles.field} style={{ flex: 1 }}>
          Платежей
          <input
            type="number"
            min={2}
            max={12}
            value={parts}
            onChange={(e) => {
              setParts(Number(e.target.value))
              setRows(null)
            }}
          />
        </label>
        <label className={layoutStyles.field} style={{ flex: 1 }}>
          Периодичность
          <Select
            value={period}
            onChange={(v) => {
              setPeriod(v as InstallmentPeriod)
              setRows(null)
            }}
            options={INSTALLMENT_PERIOD_OPTIONS}
          />
        </label>
      </div>
      <label className={layoutStyles.field}>
        {downPaymentNum > 0 ? 'Дата первого взноса и старт графика' : 'Первый платёж'}
        <DateInput
          value={firstDate}
          min={new Date().toISOString().slice(0, 10)}
          onChange={(v) => {
            setFirstDate(v)
            setRows(null)
          }}
        />
      </label>

      {rows == null ? (
        <Button type="button" variant="secondary" onClick={handlePreview} disabled={downPaymentInvalid}>
          Показать график
        </Button>
      ) : (
        <>
          <div className={styles['debt-schedule']}>
            <span className={styles['field-group-title']}>График (можно поправить вручную)</span>
            {rows.map((row, i) => (
              <div key={i} className={styles['debt-schedule-edit-row']}>
                <DateInput
                  value={row.due_date}
                  min={new Date().toISOString().slice(0, 10)}
                  onChange={(v) => setRows((prev) => prev!.map((r, j) => (j === i ? { ...r, due_date: v } : r)))}
                />
                <input
                  type="text"
                  inputMode="decimal"
                  value={row.amount}
                  onChange={(e) => {
                    const normalized = normalizeDecimalInput(e.target.value)
                    if (normalized === null) return
                    setRows((prev) => prev!.map((r, j) => (j === i ? { ...r, amount: normalized } : r)))
                  }}
                />
                <span className={layoutStyles.textMuted}>₽</span>
              </div>
            ))}
          </div>
          <p className={balanceMismatch ? layoutStyles.error : layoutStyles.textMuted}>
            Сумма графика: {formatMoney(String(rowsTotal))} ₽
            {balanceMismatch && ` — должна совпадать с остатком ${formatMoney(remainingBalance)} ₽`}
          </p>
        </>
      )}

      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button type="submit" disabled={saving || !rows || balanceMismatch}>
        {saving
          ? 'Сохранение…'
          : downPaymentNum > 0
            ? `Внести взнос и составить график на ${parts} платежа`
            : `Составить график на ${parts} платежа`}
      </Button>
    </form>
  )
}
