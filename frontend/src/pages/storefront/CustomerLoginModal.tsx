import { useEffect, useRef, useState, type FormEvent } from 'react'
import { IconBrandTelegram } from '@tabler/icons-react'
import {
  getCustomerLoginStatus,
  requestCustomerLoginLink,
  saveCustomerToken,
} from '../../entities/auth/customerApi'
import { ApiError } from '../../shared/api/client'
import { Button } from '../../shared/ui/Button'
import { Modal } from '../../shared/ui/Modal'
import { PhoneInput } from '../../shared/ui/PhoneInput'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './CustomerLoginModal.module.css'

const POLL_MS = 2000
const TOKEN_TTL_MS = 10 * 60 * 1000

interface CustomerLoginModalProps {
  onClose: () => void
  onSuccess: (accessToken: string) => void
}

export function CustomerLoginModal({ onClose, onSuccess }: CustomerLoginModalProps) {
  const [phone, setPhone] = useState('')
  const [deepLink, setDeepLink] = useState<string | null>(null)
  const [loginToken, setLoginToken] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [waiting, setWaiting] = useState(false)
  const [expired, setExpired] = useState(false)
  const startedAt = useRef<number>(0)

  useEffect(() => {
    if (!loginToken || !waiting) return
    let cancelled = false
    const tick = async () => {
      if (Date.now() - startedAt.current > TOKEN_TTL_MS) {
        setExpired(true)
        setWaiting(false)
        return
      }
      try {
        const status = await getCustomerLoginStatus(loginToken)
        if (cancelled) return
        if (status.confirmed && status.access_token) {
          saveCustomerToken(status.access_token)
          onSuccess(status.access_token)
          return
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Не удалось проверить вход')
          setWaiting(false)
        }
      }
    }
    tick()
    const id = window.setInterval(tick, POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [loginToken, waiting, onSuccess])

  async function handleRequestLink(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setExpired(false)
    setLoading(true)
    try {
      const result = await requestCustomerLoginLink(phone)
      setLoginToken(result.token)
      setDeepLink(result.telegram_deep_link)
      startedAt.current = Date.now()
      setWaiting(true)
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Не удалось запросить вход',
      )
    } finally {
      setLoading(false)
    }
  }

  function reset() {
    setDeepLink(null)
    setLoginToken(null)
    setWaiting(false)
    setExpired(false)
    setError(null)
  }

  return (
    <Modal title="Вход покупателя" onClose={onClose}>
      {!deepLink ? (
        <form className={styles.form} onSubmit={handleRequestLink}>
          <p className={styles.hint}>
            Чтобы оформить заказ, подтвердите номер через Telegram — тот же бот, что и у витрины.
          </p>
          <label className={styles.field}>
            Телефон
            <PhoneInput value={phone} onChange={setPhone} required />
          </label>
          {error && <p className={layoutStyles.error}>{error}</p>}
          <Button type="submit" disabled={loading || phone.replace(/\D/g, '').length < 10}>
            {loading ? 'Отправка…' : 'Войти через Telegram'}
          </Button>
        </form>
      ) : (
        <div className={styles.waiting}>
          <p className={styles.hint}>
            Откройте Telegram и подтвердите вход. После сообщения бота вернитесь сюда — страница
            обновится сама.
          </p>
          <a href={deepLink} target="_blank" rel="noreferrer" className={styles.tgLink}>
            <IconBrandTelegram size={18} stroke={1.8} />
            Открыть Telegram
          </a>
          {waiting && !expired && <p className={styles.poll}>Ожидаем подтверждение…</p>}
          {expired && (
            <p className={layoutStyles.error}>
              Время ссылки истекло. Запросите новую.
            </p>
          )}
          {error && <p className={layoutStyles.error}>{error}</p>}
          <Button type="button" variant="secondary" onClick={reset}>
            Другой номер
          </Button>
        </div>
      )}
    </Modal>
  )
}

export function notifyCustomerAuthChanged() {
  window.dispatchEvent(new Event('waysklad:customer-auth'))
}
