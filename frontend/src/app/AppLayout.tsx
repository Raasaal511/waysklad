import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from './AuthContext'

const NAV_ITEMS = [
  { to: '/', label: 'Продажа', icon: '💳' },
  { to: '/products', label: 'Товары', icon: '📦' },
  { to: '/stock', label: 'Остатки', icon: '🏬' },
  { to: '/orders', label: 'Заказы', icon: '📋' },
  { to: '/debts', label: 'Долги', icon: '💰' },
  { to: '/clients', label: 'Клиенты', icon: '👥' },
  { to: '/analytics', label: 'Аналитика', icon: '📊' },
  { to: '/profile', label: 'Профиль', icon: '⚙️' },
]

function NavItems({ variant }: { variant: 'sidebar' | 'bottom' }) {
  return (
    <>
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            `${variant === 'sidebar' ? 'app-sidebar-item' : 'app-nav-item'}${isActive ? ' active' : ''}`
          }
        >
          <span className={variant === 'sidebar' ? 'app-sidebar-icon' : 'app-nav-icon'}>
            {item.icon}
          </span>
          <span>{item.label}</span>
        </NavLink>
      ))}
    </>
  )
}

export function AppLayout() {
  const { user, logout } = useAuth()

  return (
    <div className="app-layout">
      <aside className="app-sidebar">
        <span className="app-title">WaySklad</span>
        <nav className="app-sidebar-nav">
          <NavItems variant="sidebar" />
        </nav>
        <div className="app-sidebar-user">
          <Link to="/profile" className="text-muted">
            {user?.name}
          </Link>
          <button type="button" className="secondary" onClick={logout}>
            Выйти
          </button>
        </div>
      </aside>

      <div className="app-main">
        <header className="app-header">
          <span className="app-title">WaySklad</span>
          <div className="app-header-user">
            <Link to="/profile" className="text-muted">
              {user?.name}
            </Link>
            <button type="button" className="secondary" onClick={logout}>
              Выйти
            </button>
          </div>
        </header>

        <main className="app-content">
          <Outlet />
        </main>

        <nav className="app-nav">
          <NavItems variant="bottom" />
        </nav>
      </div>
    </div>
  )
}
