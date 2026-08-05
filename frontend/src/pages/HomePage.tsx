import { useAuth } from '../app/AuthContext'

export function HomePage() {
  const { user, logout } = useAuth()

  return (
    <main>
      <h1>ВайСклад</h1>
      <p>
        Вы вошли как {user?.name} ({user?.role})
      </p>
      <button type="button" onClick={logout}>
        Выйти
      </button>
    </main>
  )
}
