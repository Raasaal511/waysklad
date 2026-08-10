import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../../entities/auth/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { Button } from '../../shared/ui/Button'

export function LoginPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await login(phone, password)
      auth.login(result)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось войти')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="center-screen">
      <div className="card stack">
        <div>
          <h1>WaySklad</h1>
          <p className="text-muted">Товарный учёт для малого бизнеса</p>
        </div>
        <form className="form" onSubmit={handleSubmit}>
          <label className="field">
            Телефон
            <input
              type="tel"
              placeholder="+7 928 000 00 00"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
            />
          </label>
          <label className="field">
            Пароль
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && <p className="error">{error}</p>}
          <Button type="submit" disabled={loading}>
            {loading ? 'Вход…' : 'Войти'}
          </Button>
        </form>
      </div>
    </div>
  )
}
