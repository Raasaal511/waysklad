import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { IconBrandTelegram } from '@tabler/icons-react'
import {
  getCustomerLoginStatus,
  loginCustomerWithPassword,
  registerCustomer,
  saveCustomerToken,
} from '../../entities/auth/customerApi'
import { ApiError } from '../../shared/api/client'
import { Button } from '../../shared/ui/Button'
import { PhoneInput } from '../../shared/ui/PhoneInput'
import { notifyCustomerAuthChanged } from './CustomerLoginModal'
import styles from './CustomerAuthPage.module.css'

const POLL_MS = 2000
const TOKEN_TTL_MS = 10 * 60 * 1000

type Tab = 'login' | 'register'

/**
 * Отдельная страница входа и регистрации покупателя (/store/:slug/login).
 * Модалка CustomerLoginModal остаётся там, где вход случается по ходу
 * действия — в корзине и под формой отзыва, откуда уводить со страницы нельзя.
 *
 * Регистрация: username + телефон + пароль, номер подтверждается в
 * Telegram-боте платформы — аккаунт создаётся только после этого, поэтому
 * после отправки формы страница так же опрашивает /login-status, как и вход
 * через Telegram.
 */
export function CustomerAuthPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const redirectTo = searchParams.get('next') || '/'

  const [tab, setTab] = useState<Tab>(searchParams.get('tab') === 'register' ? 'register' : 'login')

  // вход по паролю
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')

  // регистрация
  const [username, setUsername] = useState('')
  const [phone, setPhone] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regPasswordConfirm, setRegPasswordConfirm] = useState('')

  // подтверждение в Telegram — общее для регистрации и входа через бота
  const [deepLink, setDeepLink] = useState<string | null>(null)
  const [pendingToken, setPendingToken] = useState<string | null>(null)
  const [waiting, setWaiting] = useState(false)
  const [expired, setExpired] = useState(false)
  const startedAt = useRef(0)

  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  function finish(accessToken: string) {
    saveCustomerToken(accessToken)
    notifyCustomerAuthChanged()
    navigate(redirectTo, { replace: true })
  }

  useEffect(() => {
    if (!pendingToken || !waiting) return
    let cancelled = false
    const tick = async () => {
      if (Date.now() - startedAt.current > TOKEN_TTL_MS) {
        setExpired(true)
        setWaiting(false)
        return
      }
      try {
        const status = await getCustomerLoginStatus(pendingToken)
        if (cancelled) return
        if (status.confirmed && status.access_token) {
          finish(status.access_token)
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingToken, waiting])

  function startTelegramWait(token: string, link: string) {
    setPendingToken(token)
    setDeepLink(link)
    startedAt.current = Date.now()
    setExpired(false)
    setWaiting(true)
  }

  function resetTelegramWait() {
    setPendingToken(null)
    setDeepLink(null)
    setWaiting(false)
    setExpired(false)
  }

  async function submitLogin(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await loginCustomerWithPassword(login.trim(), password)
      finish(result.access_token)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось войти')
    } finally {
      setLoading(false)
    }
  }

  async function submitRegister(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await registerCustomer({
        username: username.trim(),
        phone,
        password: regPassword,
        password_confirm: regPasswordConfirm,
      })
      startTelegramWait(result.token, result.telegram_deep_link)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось зарегистрироваться')
    } finally {
      setLoading(false)
    }
  }


  // экран ожидания подтверждения — общий для обоих сценариев
  if (deepLink) {
    return (
      <div className={styles.shell}>
        <div className={styles.card}>
          <h1 className={styles.title}>Подтвердите номер</h1>
          <p className={styles.hint}>
            {tab === 'register'
              ? 'Аккаунт будет создан после подтверждения номера в Telegram — так никто не зарегистрируется на чужой телефон.'
              : 'Откройте бота в Telegram и нажмите «Старт» — так мы убедимся, что номер ваш.'}
          </p>

          <a className={styles.telegramBtn} href={deepLink} target="_blank" rel="noreferrer">
            <IconBrandTelegram size={20} stroke={1.8} />
            Открыть Telegram
          </a>

          {waiting && <p className={styles.waiting}>Ждём подтверждения…</p>}
          {expired && <p className={styles.error}>Ссылка устарела — начните заново.</p>}
          {error && <p className={styles.error}>{error}</p>}

          <button type="button" className={styles.linkBtn} onClick={resetTelegramWait}>
            Назад
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.shell}>
      <div className={styles.card}>
        <div className={styles.tabs} role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'login'}
            className={`${styles.tab} ${tab === 'login' ? styles.tabActive : ''}`}
            onClick={() => {
              setTab('login')
              setError(null)
            }}
          >
            Вход
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'register'}
            className={`${styles.tab} ${tab === 'register' ? styles.tabActive : ''}`}
            onClick={() => {
              setTab('register')
              setError(null)
            }}
          >
            Регистрация
          </button>
        </div>

        {tab === 'login' ? (
          <form className={styles.form} onSubmit={submitLogin}>
            <label className={styles.field}>
              <span className={styles.label}>Логин или телефон</span>
              <input
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                autoComplete="username"
                placeholder="vasya.01"
                required
              />
            </label>

            <label className={styles.field}>
              <span className={styles.label}>Пароль</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>

            {error && <p className={styles.error}>{error}</p>}

            <Button type="submit" disabled={loading}>
              {loading ? 'Входим…' : 'Войти'}
            </Button>
          </form>
        ) : (
          <form className={styles.form} onSubmit={submitRegister}>
            <label className={styles.field}>
              <span className={styles.label}>Логин</span>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                placeholder="vasya.01"
                required
              />
              <span className={styles.fieldHint}>
                Латиница, цифры, точка, дефис и подчёркивание, от 3 символов
              </span>
            </label>

            <label className={styles.field}>
              <span className={styles.label}>Телефон</span>
              <PhoneInput value={phone} onChange={setPhone} />
            </label>

            <label className={styles.field}>
              <span className={styles.label}>Пароль</span>
              <input
                type="password"
                value={regPassword}
                onChange={(e) => setRegPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
              <span className={styles.fieldHint}>Не короче 8 символов</span>
            </label>

            <label className={styles.field}>
              <span className={styles.label}>Повторите пароль</span>
              <input
                type="password"
                value={regPasswordConfirm}
                onChange={(e) => setRegPasswordConfirm(e.target.value)}
                autoComplete="new-password"
                required
              />
            </label>

            {error && <p className={styles.error}>{error}</p>}

            <Button type="submit" disabled={loading || !phone}>
              {loading ? 'Отправляем…' : 'Зарегистрироваться'}
            </Button>
          </form>
        )}
      </div>
    </div>
  )
}
