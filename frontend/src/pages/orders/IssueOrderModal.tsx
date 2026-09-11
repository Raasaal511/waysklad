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
  const [debtDueDate, setDebtDueDate] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const toPayCents = Math.round(Number(order.to_pay) * 100)
  const cashReceivedCents = Math.round(Number(cashReceived || 0) * 100)
  const changeCents = cashReceivedCents - toPayCents
  const change = centsToMoney(Math.max(0, changeCents))

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (payment === 'credit' && !debtDueDate) {
      setError('Для выдачи в долг укажите срок «Долг до»')
      return
    }
    setError(null)
    setSaving(true)
    try {
      const result = await issueOrder(order.id, {
        payment_method: payment,
        cash_received: payment === 'cash' && cashReceived ? cashReceived : null,
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
                if (normalized !== null) setCashReceived(normalized)
              }}
            />
            {cashReceivedCents > 0 && (
              <span className={changeCents < 0 ? 'sale-change-short' : layoutStyles.textMuted}>
                {changeCents >= 0
                  ? `Сдача: ${formatMoney(change)} ₽`
                  : `Не хватает: ${formatMoney(centsToMoney(-changeCents))} ₽`}
              </span>
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
          {saving ? 'Оформление…' : 'Выдать заказ'}
        </Button>
      </form>
    </Modal>
  )
}
