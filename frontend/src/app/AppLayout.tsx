import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { useShop } from './ShopContext'
import { useTheme } from './ThemeContext'
import { Icon, type IconName } from '../shared/ui/icons/Icon'
import { Button } from '../shared/ui/Button'
import { IconButton } from '../shared/ui/IconButton'
import type { Role } from '../entities/auth/api'

const NAV_ITEMS: { to: string; label: string; icon: IconName; roles?: Role[] }[] = [
  { to: '/', label: 'Продажи', icon: 'sale' },
  { to: '/products', label: 'Товары', icon: 'products' },
  { to: '/stock', label: 'Остатки', icon: 'stock' },
  { to: '/orders', label: 'Заказы', icon: 'orders' },
  { to: '/debts', label: 'Долги', icon: 'debts' },
  { to: '/clients', label: 'Клиенты', icon: 'clients' },
  { to: '/analytics', label: 'Аналитика', icon: 'analytics' },
  { to: '/employees', label: 'Сотрудники', icon: 'employees', roles: ['owner', 'manager'] },
]

const ROLE_LABELS: Record<Role, string> = {
  owner: 'Владелец',
  manager: 'Управляющий',
  seller: 'Продавец',
  storekeeper: 'Кладовщик',
  analyst: 'Аналитик',
}

const SIDEBAR_COLLAPSED_KEY = 'waysklad:sidebar-collapsed'

function NavItems({
  variant,
  collapsed,
  role,
}: {
  variant: 'sidebar' | 'bottom'
  collapsed?: boolean
  role?: Role
}) {
  const items = NAV_ITEMS.filter((item) => !item.roles || (role && item.roles.includes(role)))
  return (
    <>
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            `${variant === 'sidebar' ? 'app-sidebar-item' : 'app-nav-item'}${isActive ? ' active' : ''}`
          }
          data-tooltip={collapsed ? item.label : undefined}
        >
          <span className={variant === 'sidebar' ? 'app-sidebar-icon' : 'app-nav-icon'}>
            <Icon name={item.icon} size={variant === 'sidebar' ? 19 : 21} />
          </span>
          {!(variant === 'sidebar' && collapsed) && <span>{item.label}</span>}
        </NavLink>
      ))}
    </>
  )
}

function LogoMark() {
  const { mode } = useTheme()
  const src = mode === 'dark' ? '/logo-mark-dark.png' : '/logo-mark.png'
  return <img src={src} alt="WaySklad" className="app-logo-mark" />
}

function ShopTitle({ shopName }: { shopName: string }) {
  return (
    <div className="app-shop-title">
      <span className="app-shop-name">{shopName}</span>
      <span className="app-brand-tag">WaySklad</span>
    </div>
  )
}

function UserBadge({
  name,
  role,
  collapsed,
}: {
  name?: string
  role?: Role
  collapsed?: boolean
}) {
  const initial = name?.trim()?.[0]?.toUpperCase() ?? '?'
  return (
    <Link
      to="/profile"
      className="app-user-badge"
      data-tooltip={collapsed ? `${name ?? ''}${role ? ` · ${ROLE_LABELS[role]}` : ''}` : undefined}
    >
      <span className="app-user-avatar">{initial}</span>
      {!collapsed && (
        <span className="app-user-info">
          <span className="app-user-name">{name}</span>
          {role && <span className="app-user-role">{ROLE_LABELS[role]}</span>}
        </span>
      )}
    </Link>
  )
}

export function AppLayout() {
  const { user, logout } = useAuth()
  const { shopName } = useShop()
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1')
  const headerRef = useRef<HTMLElement>(null)

  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? '1' : '0')
  }, [collapsed])

  useEffect(() => {
    const el = headerRef.current
    if (!el) return
    function updateHeight() {
      if (!el) return
      const height = getComputedStyle(el).display === 'none' ? 0 : el.offsetHeight
      document.documentElement.style.setProperty('--app-header-height', `${height}px`)
    }
    updateHeight()
    const observer = new ResizeObserver(updateHeight)
    observer.observe(el)
    window.addEventListener('resize', updateHeight)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', updateHeight)
    }
  }, [])

  return (
    <div className={`app-layout${collapsed ? ' sidebar-collapsed' : ''}`}>
      <aside className="app-sidebar">
        <div className="app-sidebar-top">
          {collapsed ? (
            <LogoMark />
          ) : (
            <div className="app-shop-brand">
              <LogoMark />
              <ShopTitle shopName={shopName} />
            </div>
          )}
          <IconButton
            variant="accent"
            className="app-sidebar-toggle"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? 'Развернуть меню' : 'Свернуть меню'}
            data-tooltip={collapsed ? 'Развернуть' : undefined}
          >
            <Icon name={collapsed ? 'chevronRight' : 'chevronLeft'} size={18} />
          </IconButton>
        </div>

        <UserBadge name={user?.name} role={user?.role} collapsed={collapsed} />

        <nav className="app-sidebar-nav">
          <NavItems variant="sidebar" collapsed={collapsed} role={user?.role} />
        </nav>

        <div className="app-sidebar-footer">
          <Button
            variant="secondary"
            className="app-logout"
            onClick={logout}
            data-tooltip={collapsed ? 'Выйти' : undefined}
          >
            {collapsed ? '⏻' : 'Выйти'}
          </Button>
        </div>
      </aside>

      <div className="app-main">
        <header className="app-header" ref={headerRef}>
          <div className="app-shop-brand">
            <LogoMark />
            <ShopTitle shopName={shopName} />
          </div>
          <div className="app-header-user">
            <UserBadge name={user?.name} role={user?.role} />
            <Button variant="secondary" onClick={logout}>
              Выйти
            </Button>
          </div>
        </header>

        <main className="app-content">
          <Outlet />
        </main>

        <nav className="app-nav">
          <NavItems variant="bottom" role={user?.role} />
        </nav>
      </div>
    </div>
  )
}
