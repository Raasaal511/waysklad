import { useState } from 'react'
import type { Order } from '../../entities/order/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { Button } from '../../shared/ui/Button'
import layoutStyles from '../../shared/ui/Layout.module.css'

export function CancelOrderForm({
  order,
  onClose,
  onConfirm,
}: {
  order: Order
  onClose: () => void
  onConfirm: (reason: string) => Promise<void>
}) {
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleConfirm() {
    setSaving(true)
    setError(null)
    try {
      await onConfirm(reason)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось отменить заказ')
      setSaving(false)
    }
  }

  return (
    <Modal title={`Отменить заказ №${order.number ?? order.id}?`} onClose={onClose}>
      <div className={layoutStyles.stack}>
        <p>Резерв товара по заказу будет снят со склада. Это действие нельзя отменить.</p>
        <label className={layoutStyles.field}>
          Причина (необязательно)
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="клиент передумал…" />
        </label>
        {error && <p className={layoutStyles.error}>{error}</p>}
        <div className={layoutStyles.row} style={{ gap: 8 }}>
          <Button variant="danger" onClick={handleConfirm} disabled={saving}>
            {saving ? 'Отмена…' : 'Да, отменить заказ'}
          </Button>
          <Button variant="secondary" onClick={onClose}>
            Не отменять
          </Button>
        </div>
      </div>
    </Modal>
  )
}
