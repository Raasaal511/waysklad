import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { IconEye, IconEyeOff } from '@tabler/icons-react'
import { login, registerShop } from '../../entities/auth/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { useTheme } from '../../app/ThemeContext'
import { Button } from '../../shared/ui/Button'
import { PhoneInput } from '../../shared/ui/PhoneInput'

type Mode = 'login' | 'register'

export function LoginPage() {
  const auth = useAuth()
  const navigate = useNavigate()
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

  const [error, setError] = useState<string | null>(null)
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
      setError(err instanceof ApiError ? err.message : 'Не удалось войти')
    } finally {
      setLoading(false)
    }
  }

  async function handleRegister(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await registerShop({ shop_name: shopName, owner_name: ownerName, phone, password })
      auth.login(result, true)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось зарегистрировать магазин')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-backdrop" aria-hidden="true" />
      <div className="auth-card">
        <div className="auth-brand">
          <div className="auth-brand-row">
            <img
              src={themeMode === 'dark' ? '/logo-mark-dark.png' : '/logo-mark.png'}
              alt=""
              className="auth-logo"
            />
            <h1 className="auth-title">WaySklad</h1>
          </div>
          <p className="auth-subtitle">Товарный учёт для малого бизнеса</p>
        </div>

        <div className="auth-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'login'}
            className={`auth-tab${mode === 'login' ? ' auth-tab-active' : ''}`}
            onClick={() => switchMode('login')}
          >
            Вход
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'register'}
            className={`auth-tab${mode === 'register' ? ' auth-tab-active' : ''}`}
            onClick={() => switchMode('register')}
          >
            Регистрация
          </button>
          <span className={`auth-tab-indicator${mode === 'register' ? ' auth-tab-indicator-right' : ''}`} />
        </div>

        <div className="auth-form-viewport">
          <div className={`auth-form-track${mode === 'register' ? ' auth-form-track-register' : ''}`}>
            <form className="form auth-form" onSubmit={handleLogin} aria-hidden={mode !== 'login'}>
              <label className="field">
                Телефон
                <PhoneInput
                  value={phone}
                  onChange={setPhone}
                  required={mode === 'login'}
                  tabIndex={mode === 'login' ? 0 : -1}
                />
              </label>
              <label className="field">
                Пароль
                <div className="auth-password-field">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required={mode === 'login'}
                    tabIndex={mode === 'login' ? 0 : -1}
                  />
                  <button
                    type="button"
                    className="auth-password-toggle"
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={mode === 'login' ? 0 : -1}
                    aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                  >
                    {showPassword ? <IconEyeOff size={18} stroke={1.8} /> : <IconEye size={18} stroke={1.8} />}
                  </button>
                </div>
              </label>
              <label className="auth-remember">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  tabIndex={mode === 'login' ? 0 : -1}
                />
                Запомнить меня
              </label>
              {mode === 'login' && error && <p className="error">{error}</p>}
              <Button type="submit" disabled={loading || mode !== 'login'} tabIndex={mode === 'login' ? 0 : -1}>
                {loading && mode === 'login' ? 'Вход…' : 'Войти'}
              </Button>
            </form>

            <form className="form auth-form" onSubmit={handleRegister} aria-hidden={mode !== 'register'}>
              <label className="field">
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
              <label className="field">
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
              <label className="field">
                Телефон
                <PhoneInput
                  value={phone}
                  onChange={setPhone}
                  required={mode === 'register'}
                  tabIndex={mode === 'register' ? 0 : -1}
                />
              </label>
              <label className="field">
                Пароль
                <div className="auth-password-field">
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
                    className="auth-password-toggle"
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={mode === 'register' ? 0 : -1}
                    aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                  >
                    {showPassword ? <IconEyeOff size={18} stroke={1.8} /> : <IconEye size={18} stroke={1.8} />}
                  </button>
                </div>
              </label>
              {mode === 'register' && error && <p className="error">{error}</p>}
              <Button type="submit" disabled={loading || mode !== 'register'} tabIndex={mode === 'register' ? 0 : -1}>
                {loading && mode === 'register' ? 'Создаём магазин…' : 'Создать магазин'}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
