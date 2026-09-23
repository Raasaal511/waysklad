import { useState, type FormEvent } from 'react'
import { adminLogin } from '../../entities/admin/api'
import { ApiError } from '../../shared/api/client'
import { Button } from '../../shared/ui/Button'
import styles from './AdminLogin.module.css'

export function AdminLogin({ onSuccess }: { onSuccess: (token: string) => void }) {
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await adminLogin(login.trim(), password)
      onSuccess(result.access_token)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось войти')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.shell}>
      <form className={styles.card} onSubmit={handleSubmit}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>WS</span>
          <span>Платформа</span>
        </div>
        <h1 className={styles.title}>Вход в админ-панель</h1>
        <p className={styles.hint}>Доступ только для владельца платформы</p>

        <label className={styles.field}>
          <span className={styles.label}>Логин</span>
          <input
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            autoComplete="username"
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
          {loading ? 'Вход…' : 'Войти'}
        </Button>
      </form>
    </div>
  )
}
