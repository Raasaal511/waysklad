import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { IconEye, IconEyeOff } from '@tabler/icons-react'
import { login, registerShop } from '../../entities/auth/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { useTheme } from '../../app/ThemeContext'
import { Button } from '../../shared/ui/Button'
import { PhoneInput } from '../../shared/ui/PhoneInput'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './LoginPage.module.css'

type Mode = 'login' | 'register'

export function LoginPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const suspended = searchParams.get('reason') === 'suspended'
  // ThemeProvider уже применил на <html> сохранённые mode/accent (или дефолт light/green,
  // если на устройстве ещё никто не входил) — здесь просто читаем то же значение для логотипа
  const { mode: themeMode } = useTheme()
  const [mode, setMode] = useState<Mode>('login')

  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [showPassword, setShowPassword] = useState(false)

  const [shopName, setShopName] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [personalDataConsent, setPersonalDataConsent] = useState(false)

  const [error, setError] = useState<string | null>(
    suspended ? 'Магазин заблокирован. Доступ временно ограничен.' : null,
  )
  const [loading, setLoading] = useState(false)

  function switchMode(next: Mode) {
    setMode(next)
    setError(null)
  }

  async function handleLogin(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await login(phone, password)
      auth.login(result, remember)
      navigate('/')
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError(err.message || 'Магазин заблокирован. Доступ временно ограничен.')
      } else {
        setError(err instanceof ApiError ? err.message : 'Не удалось войти')
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleRegister(e: FormEvent) {
    e.preventDefault()
    if (!personalDataConsent) {
      setError('Нужно согласие на обработку персональных данных')
      return
    }
    setError(null)
    setLoading(true)
    try {
      const result = await registerShop({
        shop_name: shopName,
        owner_name: ownerName,
        phone,
        password,
        personal_data_consent: true,
      })
      auth.login(result, true)
      sessionStorage.setItem('waysklad:onboarding-pending', '1')
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось зарегистрировать магазин')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles['auth-screen']}>
      <div className={styles['auth-backdrop']} aria-hidden="true" />
      <div className={styles['auth-card']}>
        <div className={styles['auth-brand']}>
          <div className={styles['auth-brand-row']}>
            <img
              src={themeMode === 'dark' ? '/logo-mark-dark.png' : '/logo-mark.png'}
              alt=""
              className={styles['auth-logo']}
            />
            <h1 className={styles['auth-title']}>WaySklad</h1>
          </div>
          <p className={styles['auth-subtitle']}>Товарный учёт для малого бизнеса</p>
        </div>

        <div className={styles['auth-tabs']} role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'login'}
            className={[styles['auth-tab'], mode === 'login' && styles['auth-tab-active']].filter(Boolean).join(' ')}
            onClick={() => switchMode('login')}
          >
            Вход
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'register'}
            className={[styles['auth-tab'], mode === 'register' && styles['auth-tab-active']]
              .filter(Boolean)
              .join(' ')}
            onClick={() => switchMode('register')}
          >
            Регистрация
          </button>
          <span
            className={[styles['auth-tab-indicator'], mode === 'register' && styles['auth-tab-indicator-right']]
              .filter(Boolean)
              .join(' ')}
          />
        </div>

        <div className={styles['auth-form-viewport']}>
          <div
            className={[styles['auth-form-track'], mode === 'register' && styles['auth-form-track-register']]
              .filter(Boolean)
              .join(' ')}
          >
            <form
              className={[layoutStyles.form, styles['auth-form']].join(' ')}
              onSubmit={handleLogin}
              aria-hidden={mode !== 'login'}
            >
              <label className={layoutStyles.field}>
                Телефон
                <PhoneInput
                  value={phone}
                  onChange={setPhone}
                  required={mode === 'login'}
                  tabIndex={mode === 'login' ? 0 : -1}
                />
              </label>
              <label className={layoutStyles.field}>
                Пароль
                <div className={styles['auth-password-field']}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required={mode === 'login'}
                    tabIndex={mode === 'login' ? 0 : -1}
                  />
                  <button
                    type="button"
                    className={styles['auth-password-toggle']}
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={mode === 'login' ? 0 : -1}
                    aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                  >
                    <span key={showPassword ? 'off' : 'on'} className={styles['auth-password-toggle-icon']}>
                      {showPassword ? <IconEyeOff size={18} stroke={1.8} /> : <IconEye size={18} stroke={1.8} />}
                    </span>
                  </button>
                </div>
              </label>
              <label className={styles['auth-remember']}>
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  tabIndex={mode === 'login' ? 0 : -1}
                />
                Запомнить меня
              </label>
              {mode === 'login' && error && <p className={layoutStyles.error}>{error}</p>}
              <Button type="submit" disabled={loading || mode !== 'login'} tabIndex={mode === 'login' ? 0 : -1}>
                {loading && mode === 'login' ? 'Вход…' : 'Войти'}
              </Button>
            </form>

            <form
              className={[layoutStyles.form, styles['auth-form']].join(' ')}
              onSubmit={handleRegister}
              aria-hidden={mode !== 'register'}
            >
              <label className={layoutStyles.field}>
                Название магазина
                <input
                  type="text"
                  placeholder="Например, «Кавказ-Текстиль»"
                  value={shopName}
                  onChange={(e) => setShopName(e.target.value)}
                  required={mode === 'register'}
                  tabIndex={mode === 'register' ? 0 : -1}
                />
              </label>
              <label className={layoutStyles.field}>
                Ваше имя
                <input
                  type="text"
                  placeholder="Имя владельца"
                  value={ownerName}
                  onChange={(e) => setOwnerName(e.target.value)}
                  required={mode === 'register'}
                  tabIndex={mode === 'register' ? 0 : -1}
                />
              </label>
              <label className={layoutStyles.field}>
                Телефон
                <PhoneInput
                  value={phone}
                  onChange={setPhone}
                  required={mode === 'register'}
                  tabIndex={mode === 'register' ? 0 : -1}
                />
              </label>
              <label className={layoutStyles.field}>
                Пароль
                <div className={styles['auth-password-field']}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Не короче 6 символов"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required={mode === 'register'}
                    tabIndex={mode === 'register' ? 0 : -1}
                  />
                  <button
                    type="button"
                    className={styles['auth-password-toggle']}
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={mode === 'register' ? 0 : -1}
                    aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                  >
                    <span key={showPassword ? 'off' : 'on'} className={styles['auth-password-toggle-icon']}>
                      {showPassword ? <IconEyeOff size={18} stroke={1.8} /> : <IconEye size={18} stroke={1.8} />}
                    </span>
                  </button>
                </div>
              </label>
              <label className={styles['auth-remember']}>
                <input
                  type="checkbox"
                  checked={personalDataConsent}
                  onChange={(e) => setPersonalDataConsent(e.target.checked)}
                  tabIndex={mode === 'register' ? 0 : -1}
                  required={mode === 'register'}
                />
                <span>
                  Согласен на обработку телефона.{' '}
                  <Link to="/privacy" tabIndex={mode === 'register' ? 0 : -1}>
                    Подробнее
                  </Link>
                </span>
              </label>
              {mode === 'register' && error && <p className={layoutStyles.error}>{error}</p>}
              <Button
                type="submit"
                disabled={loading || mode !== 'register' || !personalDataConsent}
                tabIndex={mode === 'register' ? 0 : -1}
              >
                {loading && mode === 'register' ? 'Создаём магазин…' : 'Создать магазин'}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
