import { useEffect, useRef, useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import {
  IconAlertTriangle,
  IconBuildingStore,
  IconLayoutDashboard,
  IconMessageCircle,
  IconRefresh,
  IconServer,
} from '@tabler/icons-react'
import { formatRelativeTime } from '../../shared/lib/format'
import styles from './AdminLayout.module.css'

export const ADMIN_PERIODS = [
  { value: '24h', label: '24 часа', days: 1 },
  { value: '7d', label: '7 дней', days: 7 },
  { value: '30d', label: '30 дней', days: 30 },
] as const

export type AdminPeriod = (typeof ADMIN_PERIODS)[number]['value']

const SECTIONS = [
  { to: '/admin', label: 'Обзор', icon: IconLayoutDashboard, end: true },
  { to: '/admin/tenants', label: 'Магазины', icon: IconBuildingStore, end: false },
  { to: '/admin/server', label: 'Сервер', icon: IconServer, end: false },
  { to: '/admin/errors', label: 'Ошибки', icon: IconAlertTriangle, end: false },
  { to: '/admin/feedback', label: 'Обратная связь', icon: IconMessageCircle, end: false },
]

const AUTO_REFRESH_MS = 60_000

/**
 * Автообновление раздела раз в минуту. На скрытой вкладке таймер не тикает:
 * админку держат открытой часами, и фоновые запросы к платформе всё это
 * время не нужны. При возвращении на вкладку данные обновляются сразу.
 */
export function useAutoRefresh(reload: () => void, enabled = true) {
  const reloadRef = useRef(reload)
  reloadRef.current = reload

  useEffect(() => {
    if (!enabled) return
    let timer: number | undefined

    function start() {
      stop()
      timer = window.setInterval(() => reloadRef.current(), AUTO_REFRESH_MS)
    }
    function stop() {
      if (timer) window.clearInterval(timer)
      timer = undefined
    }
    function onVisibility() {
      if (document.hidden) {
        stop()
      } else {
        reloadRef.current()
        start()
      }
    }

    start()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [enabled])
}

interface AdminLayoutProps {
  title: string
  children: ReactNode
  onLogout: () => void
  version?: string
  /** Время последней успешной загрузки — показывается рядом с кнопкой обновления. */
  updatedAt?: Date | null
  onRefresh?: () => void
  refreshing?: boolean
  /** Переключатель периода — только в разделах, где он применим. */
  period?: AdminPeriod
  onPeriodChange?: (period: AdminPeriod) => void
}

export function AdminLayout({
  title,
  children,
  onLogout,
  version,
  updatedAt,
  onRefresh,
  refreshing,
  period,
  onPeriodChange,
}: AdminLayoutProps) {
  // перерисовка раз в 30 секунд, чтобы «2 минуты назад» не застывало
  const [, setTick] = useState(0)
  useEffect(() => {
    if (!updatedAt) return
    const timer = window.setInterval(() => setTick((t) => t + 1), 30_000)
    return () => window.clearInterval(timer)
  }, [updatedAt])

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>WS</span>
          <span className={styles.brandText}>Платформа</span>
        </div>

        <nav className={styles.nav}>
          {SECTIONS.map((section) => (
            <NavLink
              key={section.to}
              to={section.to}
              end={section.end}
              className={({ isActive }) =>
                `${styles.navItem} ${isActive ? styles.navItemActive : ''}`
              }
            >
              <section.icon size={18} stroke={1.8} />
              <span>{section.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className={styles.sidebarFooter}>
          <button type="button" className={styles.logout} onClick={onLogout}>
            Выйти
          </button>
          {version && <span className={styles.version}>Сборка {version}</span>}
        </div>
      </aside>

      <div className={styles.main}>
        <header className={styles.header}>
          <h1 className={styles.title}>{title}</h1>

          <div className={styles.headerActions}>
            {period && onPeriodChange && (
              <div className={styles.periods} role="group" aria-label="Период">
                {ADMIN_PERIODS.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    className={`${styles.periodBtn} ${
                      period === item.value ? styles.periodBtnActive : ''
                    }`}
                    onClick={() => onPeriodChange(item.value)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            )}

            {onRefresh && (
              <div className={styles.refresh}>
                {updatedAt && (
                  <span className={styles.updatedAt}>
                    Обновлено {formatRelativeTime(updatedAt)}
                  </span>
                )}
                <button
                  type="button"
                  className={`${styles.refreshBtn} ${refreshing ? styles.refreshBtnBusy : ''}`}
                  onClick={onRefresh}
                  aria-label="Обновить данные"
                  disabled={refreshing}
                >
                  <IconRefresh size={18} stroke={1.8} />
                </button>
              </div>
            )}
          </div>
        </header>

        <main className={styles.content}>{children}</main>
      </div>
    </div>
  )
}
