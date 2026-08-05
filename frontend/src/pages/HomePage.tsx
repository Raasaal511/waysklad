import { useAuth } from '../app/AuthContext'

export function HomePage() {
  const { user, logout } = useAuth()

  return (
    <div className="page">
      <header className="page-header">
        <h1>WaySklad</h1>
        <button type="button" className="secondary" onClick={logout}>
          Выйти
        </button>
      </header>
      <main className="page-content">
        <p>
          Вы вошли как <strong>{user?.name}</strong>
        </p>
        <p className="text-muted">Роль: {user?.role}</p>
      </main>
    </div>
  )
}
