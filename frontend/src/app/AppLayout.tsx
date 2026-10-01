import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
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
  IconPlus,
  IconDots,
  IconUser,
  IconLogout,
  IconMessageCircle,
  type Icon as TablerIcon,
} from '@tabler/icons-react'
import { useAuth } from './AuthContext'
import { useShop } from './ShopContext'
import { useTheme } from './ThemeContext'
import { useOnboarding } from './OnboardingContext'
import { NotificationBell } from './NotificationBell'
import { GlobalSearch } from './GlobalSearch'
import { Button } from '../shared/ui/Button'
import { IconButton } from '../shared/ui/IconButton'
import { FeedbackModal } from '../widgets/feedback/FeedbackModal'
import { useOfflineSync } from '../shared/offline/useOfflineSync'
import { useFeature } from '../shared/lib/useFeature'
import { useKeyboardOpen } from '../shared/lib/useKeyboardOpen'
import type { Role } from '../entities/auth/api'
import { syncPushSubscription } from '../entities/notification/push'
import styles from './AppLayout.module.css'

interface NavItem {
  to: string
  label: string
  icon: TablerIcon
  roles?: Role[]
  feature?: 'storefront'
  /** Раздел выключен флагом магазина: пункт виден неактивным и ведёт туда, где его включают. */
  locked?: boolean
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

/** Порядок вкладок в мобильной нижней панели.
 * С FAB «Продать»: 3 вкладки + кнопка + «Ещё» (как в макете).
 * Без FAB: 4 вкладки + «Ещё». Остальное — в шторке. */
const MOBILE_NAV_PRIORITY = [
  '/',
  '/products',
  '/debts',
  '/orders',
  '/stock',
  '/clients',
  '/storefront',
  '/tasks',
  '/analytics',
  '/employees',
] as const

const SELL_ROLES: Role[] = ['owner', 'manager', 'seller']
const SIDEBAR_COLLAPSED_KEY = 'waysklad:sidebar-collapsed'

const ROLE_LABELS: Record<Role, string> = {
  owner: 'Владелец',
  manager: 'Управляющий',
  seller: 'Продавец',
  storekeeper: 'Кладовщик',
  analyst: 'Аналитик',
}

/** Где владелец включает витрину — туда ведёт неактивный пункт «Витрина». */
const STOREFRONT_SETTINGS_PATH = '/profile?tab=personalization#storefront'
const STOREFRONT_LOCKED_HINT = 'Витрина выключена. Включите её в профиле, вкладка «Персонализация»'

function filterNavItems(role: Role | undefined, storefrontEnabled: boolean): NavItem[] {
  return NAV_ITEMS.flatMap((item) => {
    if (item.roles && !(role && item.roles.includes(role))) return []
    if (item.feature === 'storefront' && !storefrontEnabled) {
      // Выключенную витрину видит только владелец: включить её может только он,
      // остальным неактивный пункт был бы лишним шумом.
      return role === 'owner' ? [{ ...item, locked: true }] : []
    }
    return [item]
  })
}

/** С FAB «Продать» в баре 3 вкладки + кнопка + «Ещё» (5 слотов); без FAB — 4 вкладки + «Ещё». */
function splitMobileNav(
  items: NavItem[],
  canSell: boolean,
): { primary: NavItem[]; more: NavItem[] } {
  const byPath = new Map(items.map((item) => [item.to, item]))
  const ordered = MOBILE_NAV_PRIORITY.map((to) => byPath.get(to)).filter(
    (item): item is NavItem => item != null,
  )
  const primaryCount = canSell ? 3 : 4
  // Неактивный пункт не занимает место в нижней панели — только в шторке.
  const primary = ordered.filter((item) => !item.locked).slice(0, primaryCount)
  return {
    primary,
    more: ordered.filter((item) => !primary.includes(item)),
  }
}

function isNavActive(pathname: string, to: string): boolean {
  if (to === '/') return pathname === '/'
  return pathname === to || pathname.startsWith(`${to}/`)
}

function isMoreActive(pathname: string, moreItems: NavItem[]): boolean {
  if (pathname === '/profile' || pathname.startsWith('/profile/')) return true
  return moreItems.some((item) => isNavActive(pathname, item.to))
}

function SidebarNavItems({
  collapsed,
  role,
}: {
  collapsed?: boolean
  role?: Role
}) {
  const storefrontEnabled = useFeature('storefront')
  const items = filterNavItems(role, storefrontEnabled)
  return (
    <>
      {items.map((item) =>
        item.locked ? (
          <LockedSidebarItem key={item.to} item={item} collapsed={collapsed} />
        ) : (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            [styles['app-sidebar-item'], isActive && styles.active].filter(Boolean).join(' ')
          }
          data-tooltip={collapsed ? item.label : undefined}
          data-nav={item.to === '/tasks' ? 'tasks' : undefined}
          data-onboarding={item.to}
        >
          <span className={styles['app-sidebar-icon']}>
            <item.icon size={19} stroke={1.8} />
          </span>
          {!collapsed && <span>{item.label}</span>}
        </NavLink>
        ),
      )}
    </>
  )
}

/**
 * Неактивный пункт бокового меню (выключенная витрина). Подсказка рисуется порталом
 * с position: fixed: список пунктов прокручивается (overflow-y: auto), и обычный
 * [data-tooltip] справа от пункта он обрезает.
 */
function LockedSidebarItem({ item, collapsed }: { item: NavItem; collapsed?: boolean }) {
  const [tip, setTip] = useState<{ top: number; left: number } | null>(null)

  function show(el: HTMLElement) {
    const rect = el.getBoundingClientRect()
    setTip({ top: rect.top + rect.height / 2, left: rect.right + 10 })
  }

  return (
    <>
      <Link
        to={STOREFRONT_SETTINGS_PATH}
        className={[styles['app-sidebar-item'], styles.locked].join(' ')}
        aria-label={STOREFRONT_LOCKED_HINT}
        onMouseEnter={(e) => show(e.currentTarget)}
        onFocus={(e) => show(e.currentTarget)}
        onMouseLeave={() => setTip(null)}
        onBlur={() => setTip(null)}
      >
        <span className={styles['app-sidebar-icon']}>
          <item.icon size={19} stroke={1.8} />
        </span>
        {!collapsed && <span>{item.label}</span>}
      </Link>
      {tip &&
        createPortal(
          <div
            className={styles['app-sidebar-tooltip']}
            style={{ top: tip.top, left: tip.left }}
            role="tooltip"
          >
            {STOREFRONT_LOCKED_HINT}
          </div>,
          document.body,
        )}
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
      <span className={styles['app-shop-name']} title={shopName}>
        {shopName}
      </span>
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

function MoreSheet({
  items,
  open,
  onClose,
  onNavigate,
  onFeedback,
  onLogout,
}: {
  items: NavItem[]
  open: boolean
  onClose: () => void
  /** Переход из шторки: закрывает её без history.back(), иначе back съедает navigate. */
  onNavigate: (to: string) => void
  onFeedback: () => void
  onLogout: () => void
}) {
  const { pathname } = useLocation()
  const touchStartY = useRef<number | null>(null)

  useEffect(() => {
    if (!open) return
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className={styles['app-more-overlay']}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
      role="presentation"
    >
      <div
        className={styles['app-more-sheet']}
        role="dialog"
        aria-modal="true"
        aria-label="Ещё"
        onTouchStart={(e) => {
          touchStartY.current = e.touches[0]?.clientY ?? null
        }}
        onTouchEnd={(e) => {
          const start = touchStartY.current
          touchStartY.current = null
          if (start == null) return
          const end = e.changedTouches[0]?.clientY
          if (end != null && end - start > 64) onClose()
        }}
      >
        <div className={styles['app-more-handle']} aria-hidden="true" />
        <nav className={styles['app-more-nav']}>
          {items.map((item) => {
            if (item.locked) {
              // На телефоне нет наведения — подсказка видна строкой под названием.
              return (
                <button
                  key={item.to}
                  type="button"
                  className={[styles['app-more-item'], styles.locked].join(' ')}
                  onClick={() => onNavigate(STOREFRONT_SETTINGS_PATH)}
                >
                  <span className={styles['app-more-icon']}>
                    <item.icon size={22} stroke={1.8} />
                  </span>
                  <span className={styles['app-more-text']}>
                    <span>{item.label}</span>
                    <span className={styles['app-more-hint']}>Выключена · включить в профиле</span>
                  </span>
                </button>
              )
            }
            const isActive =
              item.to === '/'
                ? pathname === '/'
                : pathname === item.to || pathname.startsWith(`${item.to}/`)
            return (
              <button
                key={item.to}
                type="button"
                className={[styles['app-more-item'], isActive && styles.active].filter(Boolean).join(' ')}
                data-onboarding={item.to}
                data-nav={item.to === '/tasks' ? 'tasks' : undefined}
                onClick={() => onNavigate(item.to)}
              >
                <span className={styles['app-more-icon']}>
                  <item.icon size={22} stroke={1.8} />
                </span>
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>
        <div className={styles['app-more-footer']}>
          <button
            type="button"
            className={[
              styles['app-more-item'],
              (pathname === '/profile' || pathname.startsWith('/profile/')) && styles.active,
            ]
              .filter(Boolean)
              .join(' ')}
            onClick={() => onNavigate('/profile')}
          >
            <span className={styles['app-more-icon']}>
              <IconUser size={22} stroke={1.8} />
            </span>
            <span>Профиль</span>
          </button>
          <button
            type="button"
            className={styles['app-more-item']}
            onClick={() => {
              onClose()
              onFeedback()
            }}
          >
            <span className={styles['app-more-icon']}>
              <IconMessageCircle size={22} stroke={1.8} />
            </span>
            <span>Обратная связь</span>
          </button>
          <button
            type="button"
            className={styles['app-more-item']}
            onClick={() => {
              onClose()
              onLogout()
            }}
          >
            <span className={styles['app-more-icon']}>
              <IconLogout size={22} stroke={1.8} />
            </span>
            <span>Выйти</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export function AppLayout() {
  const { user, logout } = useAuth()
  const { shopName } = useShop()
  const storefrontEnabled = useFeature('storefront')
  const { active: onboardingActive, step: onboardingStep } = useOnboarding()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1')
  const [moreOpen, setMoreOpen] = useState(false)
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const openFeedback = useCallback(() => setFeedbackOpen(true), [])
  const closeFeedback = useCallback(() => setFeedbackOpen(false), [])
  const [offlineTip, setOfflineTip] = useState(false)
  const [narrowHeader, setNarrowHeader] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(max-width: 599px)').matches,
  )
  const headerRef = useRef<HTMLElement>(null)
  useKeyboardOpen()
  /** История для «назад» закрывает шторку только если её открыл пользователь (не онбординг). */
  const moreHistoryPushed = useRef(false)
  const { pendingCount, notice, dismissNotice } = useOfflineSync()
  const userId = user?.id

  // Уведомления на телефон: подтвердить серверу подписку этого браузера (после
  // смены пароля или адреса подписки она иначе перестала бы получать push).
  useEffect(() => {
    if (userId !== undefined) void syncPushSubscription(userId)
  }, [userId])

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 599px)')
    const onChange = () => setNarrowHeader(mq.matches)
    onChange()
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const canSell = user?.role != null && SELL_ROLES.includes(user.role)
  const navItems = useMemo(
    () => filterNavItems(user?.role, storefrontEnabled),
    [user?.role, storefrontEnabled],
  )
  const { primary, more } = useMemo(() => splitMobileNav(navItems, canSell), [navItems, canSell])
  const moreActive = !moreOpen && isMoreActive(pathname, more)

  const closeMore = useCallback(() => {
    setMoreOpen(false)
    if (moreHistoryPushed.current) {
      moreHistoryPushed.current = false
      if (window.history.state && (window.history.state as { moreNav?: boolean }).moreNav) {
        window.history.back()
      }
    }
  }, [])

  /** Клик по пункту шторки: нельзя звать history.back() — он откатывает сам переход. */
  const navigateFromMore = useCallback(
    (to: string) => {
      const replace = moreHistoryPushed.current
      moreHistoryPushed.current = false
      setMoreOpen(false)
      navigate(to, { replace })
    },
    [navigate],
  )

  const openMore = useCallback((withHistory: boolean) => {
    setMoreOpen(true)
    if (withHistory && !moreHistoryPushed.current) {
      window.history.pushState({ moreNav: true }, '')
      moreHistoryPushed.current = true
    }
  }, [])

  const toggleMore = useCallback(() => {
    if (moreOpen) closeMore()
    else openMore(true)
  }, [moreOpen, closeMore, openMore])

  // Онбординг: цель в «Ещё» → открыть шторку без pushState (не ломаем navigate тура).
  useEffect(() => {
    if (!onboardingActive) {
      if (moreOpen && !moreHistoryPushed.current) setMoreOpen(false)
      return
    }
    const target = onboardingStep?.target
    if (!target) return
    if (more.some((item) => item.to === target)) {
      setMoreOpen(true)
    } else if (!moreHistoryPushed.current) {
      setMoreOpen(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onboardingActive, onboardingStep?.target, more])

  useEffect(() => {
    function onPopState() {
      moreHistoryPushed.current = false
      setMoreOpen(false)
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(dismissNotice, 5000)
    return () => window.clearTimeout(timer)
  }, [notice, dismissNotice])

  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? '1' : '0')
  }, [collapsed])

  useEffect(() => {
    if (pendingCount === 0) setOfflineTip(false)
  }, [pendingCount])

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

        {/* в свёрнутом сайдбаре только иконки — строке поиска там негде жить */}
        {!collapsed && (
          <div className={styles['app-sidebar-search']}>
            <GlobalSearch />
          </div>
        )}

        <nav className={styles['app-sidebar-nav']}>
          <SidebarNavItems collapsed={collapsed} role={user?.role} />
        </nav>

        <div className={styles['app-sidebar-footer']}>
          <button
            type="button"
            className={[styles['app-sidebar-item'], styles['app-sidebar-feedback']].join(' ')}
            onClick={openFeedback}
            data-tooltip={collapsed ? 'Обратная связь' : undefined}
            aria-label={collapsed ? 'Обратная связь' : undefined}
          >
            <span className={styles['app-sidebar-icon']}>
              <IconMessageCircle size={19} stroke={1.8} />
            </span>
            {!collapsed && <span>Обратная связь</span>}
          </button>
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
          <GlobalSearch compact={narrowHeader} />
          <div className={styles['app-header-user']}>
            {pendingCount > 0 && (
              <div className={styles['app-offline-badge-wrap']}>
                <button
                  type="button"
                  className={styles['app-offline-badge']}
                  onClick={() => setOfflineTip((v) => !v)}
                  aria-expanded={offlineTip}
                  aria-label={`Не отправлено: ${pendingCount}`}
                >
                  ⏳ {pendingCount}
                </button>
                {offlineTip && (
                  <div className={styles['app-offline-tip']} role="status">
                    Продажи ждут отправки. Как появится сеть — уйдут сами.
                  </div>
                )}
              </div>
            )}
            <NotificationBell />
            <UserBadge name={user?.name} role={user?.role} collapsed={narrowHeader} />
          </div>
        </header>

        <main
          className={[styles['app-content'], canSell && styles['app-content-with-sell']]
            .filter(Boolean)
            .join(' ')}
        >
          <Outlet />
        </main>

        <nav className={styles['app-nav']}>
          {primary.map((item, index) => (
            <Fragment key={item.to}>
              {canSell && index === 2 && (
                <div className={styles['app-nav-sell']}>
                  <button
                    type="button"
                    className={styles['app-nav-sell-btn']}
                    onClick={() => navigate('/sales/new')}
                    aria-label="Продать"
                  >
                    <IconPlus size={26} stroke={2.2} />
                  </button>
                  <span className={styles['app-nav-sell-label']}>Продать</span>
                </div>
              )}
              <NavLink
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  [styles['app-nav-item'], isActive && styles.active].filter(Boolean).join(' ')
                }
                data-nav={item.to === '/tasks' ? 'tasks' : undefined}
                data-onboarding={item.to}
                aria-label={item.label}
                onClick={(e) => {
                  /* После тапа WebKit иногда оставляет outline — снимаем фокус. */
                  ;(e.currentTarget as HTMLElement).blur()
                }}
              >
                <span className={styles['app-nav-icon']}>
                  <item.icon size={21} stroke={1.8} />
                </span>
                <span>{item.label}</span>
              </NavLink>
            </Fragment>
          ))}
          {canSell && primary.length < 3 && (
            <div className={styles['app-nav-sell']}>
              <button
                type="button"
                className={styles['app-nav-sell-btn']}
                onClick={() => navigate('/sales/new')}
                aria-label="Продать"
              >
                <IconPlus size={26} stroke={2.2} />
              </button>
              <span className={styles['app-nav-sell-label']}>Продать</span>
            </div>
          )}
          <button
            type="button"
            className={[
              styles['app-nav-item'],
              (moreOpen || moreActive) && styles.active,
            ]
              .filter(Boolean)
              .join(' ')}
            onClick={toggleMore}
            aria-label="Ещё"
            aria-expanded={moreOpen}
            data-onboarding-more
          >
            <span className={styles['app-nav-icon']}>
              <IconDots size={21} stroke={1.8} />
            </span>
            <span>Ещё</span>
          </button>
        </nav>

        <MoreSheet
          items={more}
          open={moreOpen}
          onClose={closeMore}
          onNavigate={navigateFromMore}
          onFeedback={openFeedback}
          onLogout={logout}
        />

        {feedbackOpen && <FeedbackModal onClose={closeFeedback} />}
      </div>
    </div>
  )
}
