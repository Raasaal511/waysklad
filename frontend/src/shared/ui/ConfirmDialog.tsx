import { useState } from 'react'
import { Modal } from './Modal'
import { Button } from './Button'
import layoutStyles from './Layout.module.css'

export interface ConfirmDialogProps {
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  onConfirm: () => void | Promise<void>
  onClose: () => void
}

/** Модальное подтверждение действия — замена системному window.confirm,
 * оформленная в стиле остального приложения. onConfirm может быть async —
 * ждём его перед закрытием, чтобы не терять ошибку и не дать закрыть/повторно
 * нажать кнопку, пока запрос ещё выполняется. */
export function ConfirmDialog({
  title,
  message,
  confirmLabel = 'Подтвердить',
  cancelLabel = 'Отмена',
  danger,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleConfirm() {
    setPending(true)
    setError(null)
    try {
      await onConfirm()
      onClose()
    } catch {
      setError('Не удалось выполнить действие. Попробуйте ещё раз.')
      setPending(false)
    }
  }

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            {cancelLabel}
          </Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={handleConfirm} disabled={pending}>
            {pending ? 'Подождите…' : confirmLabel}
          </Button>
        </>
      }
    >
      <p>{message}</p>
      {error && <p className={layoutStyles.error}>{error}</p>}
    </Modal>
  )
}
