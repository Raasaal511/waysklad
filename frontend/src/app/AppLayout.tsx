import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import {
  IconShoppingCart,
  IconBox,
  IconBuildingWarehouse,
  IconClipboardList,
  IconChecklist,
  IconCash,
  IconUsers,
  IconChartBar,
  IconUserCog,
  IconHistory,
  IconChevronLeft,
  IconChevronRight,
  type Icon as TablerIcon,
} from '@tabler/icons-react'
import { useAuth } from './AuthContext'
import { useShop } from './ShopContext'
import { useTheme } from './ThemeContext'
import { NotificationBell } from './NotificationBell'
import { Button } from '../shared/ui/Button'
import { IconButton } from '../shared/ui/IconButton'
import { useOfflineSync } from '../shared/offline/useOfflineSync'
import type { Role } from '../entities/auth/api'

interface NavItem {
  to: string
  label: string
  icon: TablerIcon
  roles?: Role[]
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Продажи', icon: IconShoppingCart, roles: ['owner', 'manager', 'seller'] },
  { to: '/products', label: 'Товары', icon: IconBox },
  { to: '/stock', label: 'Склады', icon: IconBuildingWarehouse },
  {
    to: '/orders', label: 'Заказы', icon: IconClipboardList,
    roles: ['owner', 'manager', 'seller', 'analyst'],
  },
  { to: '/tasks', label: 'Задачи', icon: IconChecklist },
  {
    to: '/debts', label: 'Долги', icon: IconCash,
    roles: ['owner', 'manager', 'seller', 'analyst'],
  },
  {
    to: '/clients', label: 'Клиенты', icon: IconUsers,
    roles: ['owner', 'manager', 'seller', 'analyst'],
  },
  { to: '/analytics', label: 'Аналитика', icon: IconChartBar, roles: ['owner', 'manager', 'analyst'] },
  { to: '/employees', label: 'Сотрудники', icon: IconUserCog, roles: ['owner', 'manager'] },
  // видно только ролям с Permission.AUDIT_VIEW (backend/app/domain/identity/permissions.py)
  { to: '/audit', label: 'Журнал', icon: IconHistory, roles: ['owner', 'analyst'] },
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
          data-nav={item.to === '/tasks' ? 'tasks' : undefined}
        >
          <span className={variant === 'sidebar' ? 'app-sidebar-icon' : 'app-nav-icon'}>
            <item.icon size={variant === 'sidebar' ? 19 : 21} stroke={1.8} />
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
  const { pendingCount, notice, dismissNotice } = useOfflineSync()

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(dismissNotice, 5000)
    return () => window.clearTimeout(timer)
  }, [notice, dismissNotice])

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
      {notice && (
        <div className={`app-offline-toast app-offline-toast-${notice.kind}`} role="status">
          {notice.message}
          <button
            type="button"
            className="app-offline-toast-close"
            onClick={dismissNotice}
            aria-label="Закрыть"
          >
            ×
          </button>
        </div>
      )}
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
          <div className="app-sidebar-top-actions">
            <NotificationBell align="left" />
            <IconButton
              variant="accent"
              className="app-sidebar-toggle"
              onClick={() => setCollapsed((v) => !v)}
              aria-label={collapsed ? 'Развернуть меню' : 'Свернуть меню'}
              data-tooltip={collapsed ? 'Развернуть' : undefined}
            >
              {collapsed ? <IconChevronRight size={18} stroke={1.8} /> : <IconChevronLeft size={18} stroke={1.8} />}
            </IconButton>
          </div>
        </div>

        <UserBadge name={user?.name} role={user?.role} collapsed={collapsed} />
        {pendingCount > 0 && (
          <div className="app-offline-pending" data-tooltip="Продажи, ожидающие отправки на сервер">
            {collapsed ? pendingCount : `Не отправлено: ${pendingCount}`}
          </div>
        )}

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
            <NotificationBell />
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
