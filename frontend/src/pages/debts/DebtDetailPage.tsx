import { Fragment, useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  getDebt,
  repayDebt,
  extendDebt,
  createInstallment,
  type Debt,
} from '../../entities/debt/api'
import { searchClients, listSuppliers, type Client, type Supplier } from '../../entities/counterparty/api'
import { getSale, type Sale } from '../../entities/sale/api'
import { listDocuments, type DocumentHistoryEntry } from '../../entities/inventory/api'
import { listAllProducts, type Product } from '../../entities/product/api'
import {
  type InstallmentPeriod,
  INSTALLMENT_PERIOD_OPTIONS,
  buildInstallmentSchedule,
} from '../../entities/debt/installmentSchedule'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import {
  IconChevronLeft,
  IconUser,
  IconTruck,
  IconReceipt,
  IconCheck,
  IconCalendarDue,
  IconCash,
  IconCalendarTime,
  IconCalendarRepeat,
} from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
import { InfoHint } from '../../shared/ui/InfoHint'
import { formatMoney, formatQuantity, normalizeDecimalInput } from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from '../../entities/debt/debtStatus'
import { daysOverdue, pluralDays } from '../../entities/debt/dueDate'

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('ru-RU')
}

function DueDateLabel({ dueDate, prefix = 'срок до' }: { dueDate: string; prefix?: string }) {
  const overdue = daysOverdue(dueDate)
  if (overdue > 0) {
    return (
      <span className="text-danger">
        просрочен на {overdue} {pluralDays(overdue)}
      </span>
    )
  }
  if (overdue === 0) {
    return <span className="text-warning">срок сегодня</span>
  }
  return (
    <span>
      {prefix} {formatDate(dueDate)}
    </span>
  )
}

// Прогресс оплаты как ряд мелких дробных сегментов вместо сплошной полоски —
// segments задаёт число делений (для рассрочки — по числу платежей), dueDate
// рисует финальную точку-цель (срок выплаты) в конце ряда.
function DottedProgress({
  segments,
  filled,
  dueDate,
}: {
  segments: number
  filled: number
  dueDate?: string | null
}) {
  return (
    <div className="debt-pay-progress-dots">
      {Array.from({ length: segments }, (_, i) => (
        <Fragment key={i}>
          {i > 0 && i === filled && filled < segments && (
            <span className="debt-pay-progress-divider" title="Оплачено · осталось выплатить" />
          )}
          <span className={`debt-pay-progress-dot${i < filled ? ' debt-pay-progress-dot-filled' : ''}`} />
        </Fragment>
      ))}
      <span
        className={`debt-pay-progress-goal${filled >= segments ? ' debt-pay-progress-goal-reached' : ''}`}
        title={dueDate ? `Срок ${formatDate(dueDate)}` : 'Полное погашение'}
      >
        {filled >= segments && <IconCheck size={8} stroke={3} />}
      </span>
    </div>
  )
}

export function DebtDetailPage() {
  const { id } = useParams<{ id: string }>()
  const debtId = Number(id)

  const [debt, setDebt] = useState<Debt | null>(null)
  const [clients, setClients] = useState<Client[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showRepay, setShowRepay] = useState(false)
  const [showExtend, setShowExtend] = useState(false)
  const [showInstallment, setShowInstallment] = useState(false)
  const [sale, setSale] = useState<Sale | null>(null)
  const [receiptDocument, setReceiptDocument] = useState<DocumentHistoryEntry | null>(null)
  const [products, setProducts] = useState<Product[]>([])

  async function load() {
    setLoading(true)
    try {
      const [d, clientList, supplierList] = await Promise.all([
        getDebt(debtId),
        searchClients(),
        listSuppliers(),
      ])
      setDebt(d)
      setClients(clientList)
      setSuppliers(supplierList)
      if (d.sale_id != null) {
        const [s, productList] = await Promise.all([getSale(d.sale_id), listAllProducts()])
        setSale(s)
        setReceiptDocument(null)
        setProducts(productList)
      } else if (d.receipt_document_id != null) {
        const [documents, productList] = await Promise.all([listDocuments(), listAllProducts()])
        setSale(null)
        setReceiptDocument(documents.find((doc) => doc.id === d.receipt_document_id) ?? null)
        setProducts(productList)
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

  const counterpartyName = (d: Debt) =>
    d.client_id
      ? clients.find((c) => c.id === d.client_id)?.name ?? `Клиент #${d.client_id}`
      : suppliers.find((s) => s.id === d.supplier_id)?.name ?? `Поставщик #${d.supplier_id}`

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

  const Icon = debt?.client_id != null ? IconUser : IconTruck

  return (
    <div className="stack">
      <Link to="/debts" className="back-link">
        <IconChevronLeft size={16} stroke={1.8} /> Все долги
      </Link>

      {loading || !debt ? (
        <p className="text-muted">Загрузка…</p>
      ) : (
        <>
          <div className="section-title">
            <div className="stack" style={{ gap: 2 }}>
              <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                <span className="debt-group-icon">
                  <Icon size={18} stroke={1.8} />
                </span>
                <h2>{counterpartyName(debt)}</h2>
                <span className={DEBT_STATUS_BADGE_CLASS[debt.status]}>{DEBT_STATUS_LABELS[debt.status]}</span>
              </div>
              <span className="text-muted">
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

          <div className="debt-pay-progress">
            <span className="debt-pay-progress-paid">Оплачено {formatMoney(debt.repaid)} ₽</span>
            <DottedProgress
              segments={20}
              filled={Math.round(
                Math.min(1, Number(debt.repaid) / Math.max(Number(debt.amount), 1)) * 20,
              )}
              dueDate={debt.due_date}
            />
            <div className="debt-pay-progress-labels">
              <span className="debt-pay-progress-balance">
                Остаток {formatMoney(debt.balance)} ₽ <span className="text-muted">из {formatMoney(debt.amount)} ₽</span>
              </span>
            </div>
          </div>

          <span className="debt-item-source">
            {debt.sale_id != null ? (
              <Link to={`/?openSale=${debt.sale_id}`} className="debt-item-source-link">
                <IconReceipt size={13} stroke={1.8} /> Из продажи №{debt.sale_id}
              </Link>
            ) : debt.receipt_document_id != null ? (
              <span className="text-muted">
                <IconReceipt size={13} stroke={1.8} /> Из приёмки №
                {receiptDocument?.number ?? debt.receipt_document_id}
              </span>
            ) : debt.note ? (
              <span className="text-muted">{debt.note}</span>
            ) : (
              <span className="text-muted">Выдан вручную</span>
            )}
          </span>

          {sale && sale.lines.length > 0 && (
            <div className="card card-full stack">
              <h3>Товары из продажи</h3>
              <div className="debt-schedule">
                {sale.lines.map((line) => (
                  <div key={line.id} className="debt-schedule-row">
                    <span>
                      {products.find((p) => p.id === line.product_id)?.name ?? `Товар #${line.product_id}`}
                      <span className="text-muted"> × {formatQuantity(line.quantity)}</span>
                    </span>
                    <span>{formatMoney(line.total)} ₽</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {receiptDocument && receiptDocument.lines.length > 0 && (
            <div className="card card-full stack">
              <h3>Товары из приёмки</h3>
              <div className="debt-schedule">
                {receiptDocument.lines.map((line, i) => (
                  <div key={i} className="debt-schedule-row">
                    <span>
                      {products.find((p) => p.id === line.product_id)?.name ?? `Товар #${line.product_id}`}
                      <span className="text-muted"> × {formatQuantity(line.quantity)}</span>
                    </span>
                    <span>
                      {line.cost != null ? `${formatMoney(String(Number(line.cost) * Number(line.quantity)))} ₽` : '—'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!debt.is_closed && (
            <div className="debt-detail-actions">
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
                  load()
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
                    <span className="modal-title-sub">сейчас до {formatDate(debt.due_date)}</span>
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
                  load()
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
                  load()
                }}
              />
            </Modal>
          )}

          {debt.schedule.length > 0 && (
            <div className="card card-full stack">
              <h3>График рассрочки</h3>
              <InstallmentSchedule debt={debt} onDone={load} />
            </div>
          )}

          {debt.schedule.length === 0 && debt.repayments.length > 0 && (
            <div className="card card-full stack">
              <div className="debt-payments-header">
                <h3>Оплаты</h3>
                <span className="debt-payments-total">
                  {formatMoney(String(debt.repayments.reduce((sum, r) => sum + Number(r.amount), 0)))} ₽
                </span>
              </div>
              <div className="debt-payments-list">
                {[...debt.repayments]
                  .sort((a, b) => b.on.localeCompare(a.on))
                  .map((r, i) => (
                    <div key={i} className="debt-payment-row">
                      <span className="debt-payment-dot" />
                      <div className="debt-payment-main">
                        <span className="debt-payment-date">{formatDate(r.on)}</span>
                        {r.note && <span className="debt-payment-note">{r.note}</span>}
                      </div>
                      <strong className="debt-payment-amount">{formatMoney(r.amount)} ₽</strong>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </>
      )}
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
    <form className="form debt-detail-form" onSubmit={handleSubmit}>
      <p className="text-muted debt-form-hint-row">
        Остаток долга: {formatMoney(balance)} ₽
        <InfoHint text="Разовый платёж без графика — просто уменьшает долг на внесённую сумму." />
      </p>
      <label className="field">
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
      <label className="field">
        Дата оплаты
        <DateInput value={paidOn} onChange={setPaidOn} max={new Date().toISOString().slice(0, 10)} />
      </label>
      <label className="field">
        Комментарий
        <input placeholder="Необязательно" value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      {willClose && (
        <p className="debt-close-hint">Этой суммой долг будет погашен полностью — статус станет «Погашен».</p>
      )}
      {error && <p className="error">{error}</p>}
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

  // Прямой связи Repayment→InstallmentPayment в данных нет, поэтому и
  // "оплачен ли платёж", и "какой датой" определяем одной и той же
  // эвристикой: оплаты по порядку дат покрывают строки графика по порядку.
  // paidOn строки — дата той оплаты, которая закрыла её последней (может
  // отличаться от плановой due_date, если заплатили раньше/позже или другой
  // суммой).
  const sortedRepayments = [...debt.repayments].sort((a, b) => a.on.localeCompare(b.on))
  let paidSoFar = 0
  let repaymentIndex = 0
  const rows = debt.schedule.map((s) => {
    const amount = Number(s.amount)
    let paidOn: string | null = null
    while (paidSoFar < amount - 0.01 && repaymentIndex < sortedRepayments.length) {
      paidSoFar += Number(sortedRepayments[repaymentIndex].amount)
      paidOn = sortedRepayments[repaymentIndex].on
      repaymentIndex += 1
    }
    const paid = paidSoFar >= amount - 0.01
    if (paid) paidSoFar -= amount
    return { ...s, paid, paidOn: paid ? paidOn : null }
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
    const remainingAfterThis = rows.slice(index).reduce((sum, r) => sum + Number(r.amount), 0)
    return Number(payAmount) >= remainingAfterThis - 0.01
  }

  return (
    <div className="stack">
      <div className="debt-pay-progress">
        <DottedProgress
          segments={rows.length}
          filled={paidCount}
          dueDate={rows[rows.length - 1]?.due_date}
        />
        <div className="debt-pay-progress-labels">
          <span>Оплачено {paidCount} из {rows.length}</span>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="debt-installment-list">
        <div className="debt-installment-head">
          <span>Дата выплаты</span>
          <span>Фактическая выплата</span>
          <span>Сумма</span>
          <span>Статус</span>
        </div>
        {rows.map((s, i) => (
          <div key={i} className="debt-installment-row">
            <div className={`debt-installment-cols${s.paid ? ' debt-schedule-row-paid' : ''}`}>
              <span>
                {formatDate(s.due_date)}
                {!s.paid && daysOverdue(s.due_date) > 0 && (
                  <>
                    {' '}
                    <span className="text-danger">· просрочен на {daysOverdue(s.due_date)} {pluralDays(daysOverdue(s.due_date))}</span>
                  </>
                )}
              </span>
              <span className={s.paidOn && s.paidOn !== s.due_date ? 'debt-installment-paid-on-diff' : 'text-muted'}>
                {s.paidOn ? formatDate(s.paidOn) : '—'}
              </span>
              <span>{formatMoney(s.amount)} ₽</span>
              <span
                className={`debt-schedule-row-status ${s.paid ? 'badge accent' : !s.paid && daysOverdue(s.due_date) > 0 ? 'badge danger' : 'badge'}`}
              >
                {s.paid ? 'Оплачен' : daysOverdue(s.due_date) > 0 ? 'Просрочен' : i === nextUnpaidIndex ? 'Следующий' : 'Ожидает'}
              </span>
            </div>
            {!s.paid && payingIndex === i && (
              <div className="debt-installment-pay-form">
                <label className="field">
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
                <label className="field">
                  Дата оплаты
                  <DateInput value={payDate} onChange={setPayDate} max={new Date().toISOString().slice(0, 10)} />
                </label>
                {debtWillClose(i) && (
                  <p className="debt-close-hint debt-installment-close-hint">
                    Этой суммой долг будет погашен полностью — статус станет «Погашен».
                  </p>
                )}
                <div className="debt-installment-row-actions">
                  <Button onClick={() => markPaid(i)} disabled={!payAmount || !payDate || savingIndex === i}>
                    {savingIndex === i ? 'Сохранение…' : 'Подтвердить'}
                  </Button>
                  <Button variant="secondary" onClick={() => setPayingIndex(null)}>
                    Отмена
                  </Button>
                </div>
              </div>
            )}
            {!s.paid && payingIndex !== i && (
              <div className="debt-installment-row-actions">
                <Button
                  variant="secondary"
                  onClick={() => {
                    setPayingIndex(i)
                    setPayAmount(s.amount)
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
    <form className="form debt-detail-form" onSubmit={handleSubmit}>
      <p className="text-muted debt-form-hint-row">
        Текущий остаток долга: {formatMoney(balance)} ₽
        <InfoHint text="Переносит общий срок «Долг до» на другую дату." />
      </p>
      {hasSchedule && (
        <p className="debt-extend-warning">
          У долга есть график рассрочки — продление меняет только общий срок «Долг до», сроки
          отдельных платежей графика останутся прежними. Перенести конкретный платёж можно
          в самом графике.
        </p>
      )}
      <label className="field">
        Новый срок «Долг до»
        <DateInput
          value={newDueDate}
          onChange={setNewDueDate}
          min={new Date().toISOString().slice(0, 10)}
          required
        />
      </label>
      <label className="field">
        Причина
        <input
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Например: попросил ещё неделю"
        />
      </label>
      {error && <p className="error">{error}</p>}
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
    <form className="form debt-detail-form" onSubmit={handleSubmit}>
      <p className="text-muted debt-form-hint-row">
        Остаток к разбивке: {formatMoney(balance)} ₽
        <InfoHint text="Разбивает остаток на платежи по датам — чтобы видеть график и не забыть сроки." />
      </p>
      <label className="field">
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
        <p className={downPaymentInvalid ? 'error' : 'text-muted'}>
          {downPaymentInvalid
            ? 'Первый взнос должен быть меньше остатка долга'
            : `В рассрочку пойдёт ${formatMoney(remainingBalance)} ₽`}
        </p>
      )}
      <div className="row">
        <label className="field" style={{ flex: 1 }}>
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
        <label className="field" style={{ flex: 1 }}>
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
      <label className="field">
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
          <div className="debt-schedule">
            <span className="field-group-title">График (можно поправить вручную)</span>
            {rows.map((row, i) => (
              <div key={i} className="debt-schedule-edit-row">
                <DateInput
                  value={row.due_date}
                  min={new Date().toISOString().slice(0, 10)}
                  onChange={(v) =>
                    setRows((prev) => prev!.map((r, j) => (j === i ? { ...r, due_date: v } : r)))
                  }
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
                <span className="text-muted">₽</span>
              </div>
            ))}
          </div>
          <p className={balanceMismatch ? 'error' : 'text-muted'}>
            Сумма графика: {formatMoney(String(rowsTotal))} ₽
            {balanceMismatch && ` — должна совпадать с остатком ${formatMoney(remainingBalance)} ₽`}
          </p>
        </>
      )}

      {error && <p className="error">{error}</p>}
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
