import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from './AuthContext'

const NAV_ITEMS = [
  { to: '/', label: 'Продажа', icon: '💳' },
  { to: '/products', label: 'Товары', icon: '📦' },
  { to: '/stock', label: 'Остатки', icon: '🏬' },
  { to: '/orders', label: 'Заказы', icon: '📋' },
  { to: '/debts', label: 'Долги', icon: '💰' },
  { to: '/clients', label: 'Клиенты', icon: '👥' },
  { to: '/analytics', label: 'Аналитика', icon: '📊' },
]

export function AppLayout() {
  const { user, logout } = useAuth()

  return (
    <div className="app-layout">
      <header className="app-header">
        <span className="app-title">WaySklad</span>
        <div className="app-header-user">
          <span className="text-muted">{user?.name}</span>
          <button type="button" className="secondary" onClick={logout}>
            Выйти
          </button>
        </div>
      </header>

      <main className="app-content">
        <Outlet />
      </main>

      <nav className="app-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => `app-nav-item${isActive ? ' active' : ''}`}
          >
            <span className="app-nav-icon">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
