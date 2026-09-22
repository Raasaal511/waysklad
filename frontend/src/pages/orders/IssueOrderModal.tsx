import { useState, type FormEvent } from 'react'
import { issueOrder, type IssueOrderResult, type Order } from '../../entities/order/api'
import { useCatalog } from '../../app/CatalogContext'
import type { PaymentMethod } from '../../entities/sale/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
import {
  formatMoney,
  normalizeDecimalInput,
  centsToMoney,
} from '../../shared/lib/format'
import { PAYMENT_LABELS } from '../sales/saleDraft'
import layoutStyles from '../../shared/ui/Layout.module.css'

export function IssueOrderModal({
  order,
  onClose,
  onIssued,
}: {
  order: Order
  onClose: () => void
  onIssued: (result: IssueOrderResult) => void
}) {
  const { refresh: refreshCatalog } = useCatalog()
  const [payment, setPayment] = useState<PaymentMethod>('cash')
  const [cashReceived, setCashReceived] = useState('')
  const [keepChange, setKeepChange] = useState(false)
  const [debtDueDate, setDebtDueDate] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toPayCents = Math.round(Number(order.to_pay) * 100)
  const cashReceivedCents = Math.round(Number(cashReceived || 0) * 100)
  const rawChangeCents = cashReceivedCents - toPayCents
  const changeKeptCents = keepChange && rawChangeCents > 0 ? rawChangeCents : 0
  const changeCents = rawChangeCents - changeKeptCents
  const change = centsToMoney(Math.max(0, changeCents))
  const changeKept = centsToMoney(changeKeptCents)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (payment === 'credit' && !debtDueDate) {
      setError('Для выдачи в долг укажите срок «Долг до»')
      return
    }
    setError(null)
    setSaving(true)
    try {
      const cashReceivedValue = payment === 'cash' && cashReceived ? cashReceived : null
      const result = await issueOrder(order.id, {
        payment_method: payment,
        cash_received: cashReceivedValue,
        change_kept:
          cashReceivedValue && changeKeptCents > 0
            ? centsToMoney(changeKeptCents).toFixed(2)
            : '0',
        debt_due_date: payment === 'credit' ? debtDueDate : null,
      })
      refreshCatalog(['stock']).catch(() => {})
      onIssued(result)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось выдать заказ')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={`Выдать заказ №${order.number ?? order.id}`} onClose={onClose}>
      <form className={layoutStyles.form} onSubmit={handleSubmit}>
        <div className="sale-detail-totals">
          <div className="sale-detail-totals-row">
            <span>Сумма заказа</span>
            <span>{formatMoney(order.total)} ₽</span>
          </div>
          {Number(order.prepayment) > 0 && (
            <div className="sale-detail-totals-row">
              <span>Предоплата</span>
              <span>−{formatMoney(order.prepayment)} ₽</span>
            </div>
          )}
          <div className="sale-detail-totals-row sale-detail-totals-row-sum">
            <span>К оплате сейчас</span>
            <span>{formatMoney(order.to_pay)} ₽</span>
          </div>
        </div>

        <label className={layoutStyles.field}>
          Способ оплаты
          <Select
            value={payment}
            onChange={(v) => setPayment(v as PaymentMethod)}
            options={Object.entries(PAYMENT_LABELS).map(([value, label]) => ({ value, label }))}
          />
        </label>

        {payment === 'cash' && (
          <label className={layoutStyles.field}>
            Получено
            <input
              type="text"
              inputMode="decimal"
              placeholder={formatMoney(order.to_pay)}
              value={cashReceived}
              onChange={(e) => {
                const normalized = normalizeDecimalInput(e.target.value)
                if (normalized !== null) {
                  setCashReceived(normalized)
                  setKeepChange(false)
                }
              }}
            />
            {cashReceivedCents > 0 && (
              <span className={rawChangeCents < 0 ? 'sale-change-short' : layoutStyles.textMuted}>
                {rawChangeCents < 0
                  ? `Не хватает: ${formatMoney(centsToMoney(-rawChangeCents))} ₽`
                  : keepChange
                    ? `Сдача не выдана · осталось в кассе ${formatMoney(changeKept)} ₽`
                    : `Сдача: ${formatMoney(change)} ₽`}
              </span>
            )}
            {rawChangeCents > 0 && (
              <label
                className={layoutStyles.row}
                style={{ gap: 8, marginTop: 4, fontSize: 13, fontWeight: 500 }}
              >
                <input
                  type="checkbox"
                  checked={keepChange}
                  onChange={(e) => setKeepChange(e.target.checked)}
                />
                Клиент не взял сдачу
              </label>
            )}
          </label>
        )}

        {payment === 'credit' && (
          <label className={layoutStyles.field}>
            Долг до
            <DateInput
              required
              value={debtDueDate}
              min={new Date().toISOString().slice(0, 10)}
              onChange={setDebtDueDate}
            />
          </label>
        )}

        {error && <p className={layoutStyles.error}>{error}</p>}
        <Button type="submit" disabled={saving}>
          {saving ? 'Выдача…' : 'Выдать'}
        </Button>
      </form>
    </Modal>
  )
}
