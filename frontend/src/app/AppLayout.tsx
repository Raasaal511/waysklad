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
  IconBuildingStore,
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
import { useFeature } from '../shared/lib/useFeature'
import type { Role } from '../entities/auth/api'
import styles from './AppLayout.module.css'

interface NavItem {
  to: string
  label: string
  icon: TablerIcon
  roles?: Role[]
  feature?: 'storefront'
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Продажи', icon: IconShoppingCart, roles: ['owner', 'manager', 'seller'] },
  { to: '/products', label: 'Товары', icon: IconBox },
  { to: '/stock', label: 'Склады', icon: IconBuildingWarehouse },
  {
    to: '/orders', label: 'Заказы', icon: IconClipboardList,
    roles: ['owner', 'manager', 'seller', 'analyst'],
  },
  {
    to: '/storefront', label: 'Витрина', icon: IconBuildingStore,
    roles: ['owner', 'manager', 'seller'], feature: 'storefront',
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
  const storefrontEnabled = useFeature('storefront')
  const items = NAV_ITEMS.filter(
    (item) =>
      (!item.roles || (role && item.roles.includes(role))) &&
      (item.feature !== 'storefront' || storefrontEnabled),
  )
  return (
    <>
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            [
              variant === 'sidebar' ? styles['app-sidebar-item'] : styles['app-nav-item'],
              isActive && styles.active,
            ]
              .filter(Boolean)
              .join(' ')
          }
          data-tooltip={collapsed ? item.label : undefined}
          data-nav={item.to === '/tasks' ? 'tasks' : undefined}
          data-onboarding={item.to}
          aria-label={variant === 'bottom' ? item.label : undefined}
        >
          <span className={variant === 'sidebar' ? styles['app-sidebar-icon'] : styles['app-nav-icon']}>
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
  return <img src={src} alt="WaySklad" className={styles['app-logo-mark']} />
}

function ShopTitle({ shopName }: { shopName: string }) {
  return (
    <div className={styles['app-shop-title']}>
      <span className={styles['app-shop-name']}>{shopName}</span>
      <span className={styles['app-brand-tag']}>WaySklad</span>
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
      className={styles['app-user-badge']}
      data-tooltip={collapsed ? `${name ?? ''}${role ? ` · ${ROLE_LABELS[role]}` : ''}` : undefined}
    >
      <span className={styles['app-user-avatar']}>{initial}</span>
      {!collapsed && (
        <span className={styles['app-user-info']}>
          <span className={styles['app-user-name']}>{name}</span>
          {role && <span className={styles['app-user-role']}>{ROLE_LABELS[role]}</span>}
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
    <div className={[styles['app-layout'], collapsed && styles['sidebar-collapsed']].filter(Boolean).join(' ')}>
      {notice && (
        <div
          className={[styles['app-offline-toast'], styles[`app-offline-toast-${notice.kind}`]].join(' ')}
          role="status"
        >
          {notice.message}
          <button
            type="button"
            className={styles['app-offline-toast-close']}
            onClick={dismissNotice}
            aria-label="Закрыть"
          >
            ×
          </button>
        </div>
      )}
      <aside className={styles['app-sidebar']}>
        <div className={styles['app-sidebar-top']}>
          {collapsed ? (
            <LogoMark />
          ) : (
            <div className={styles['app-shop-brand']}>
              <LogoMark />
              <ShopTitle shopName={shopName} />
            </div>
          )}
          <div className={styles['app-sidebar-top-actions']}>
            <NotificationBell align="left" />
            <IconButton
              variant="accent"
              className={styles['app-sidebar-toggle']}
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
          <div className={styles['app-offline-pending']} data-tooltip="Продажи, ожидающие отправки на сервер">
            {collapsed ? pendingCount : `Не отправлено: ${pendingCount}`}
          </div>
        )}

        <nav className={styles['app-sidebar-nav']}>
          <NavItems variant="sidebar" collapsed={collapsed} role={user?.role} />
        </nav>

        <div className={styles['app-sidebar-footer']}>
          <Button
            variant="secondary"
            className={styles['app-logout']}
            onClick={logout}
            data-tooltip={collapsed ? 'Выйти' : undefined}
          >
            {collapsed ? '⏻' : 'Выйти'}
          </Button>
        </div>
      </aside>

      <div className={styles['app-main']}>
        <header className={styles['app-header']} ref={headerRef}>
          <div className={styles['app-shop-brand']}>
            <LogoMark />
            <ShopTitle shopName={shopName} />
          </div>
          <div className={styles['app-header-user']}>
            <NotificationBell />
            <UserBadge name={user?.name} role={user?.role} />
            <Button variant="secondary" onClick={logout}>
              Выйти
            </Button>
          </div>
        </header>

        <main className={styles['app-content']}>
          <Outlet />
        </main>

        <nav className={styles['app-nav']}>
          <NavItems variant="bottom" role={user?.role} />
        </nav>
      </div>
    </div>
  )
}
