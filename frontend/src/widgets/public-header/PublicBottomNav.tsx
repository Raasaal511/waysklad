import { useEffect, useState } from 'react'
import { Link, matchPath, useLocation } from 'react-router-dom'
import {
  IconHeart,
  IconLayoutGrid,
  IconShoppingCart,
  IconUserCircle,
} from '@tabler/icons-react'
import { loadCustomerToken } from '../../entities/auth/customerApi'
import { FAVORITES_EVENT } from '../../shared/lib/favorites'
import { cartCountForSlug, favoritesCountForSlug } from '../../shared/lib/storefrontCounters'
import styles from './PublicBottomNav.module.css'

const STORE_ROUTE = '/store/:slug/*'

interface NavItemProps {
  to: string
  label: string
  active: boolean
  count?: number
  children: React.ReactNode
}

function NavItem({ to, label, active, count, children }: NavItemProps) {
  return (
    <Link to={to} className={`${styles.item} ${active ? styles.itemActive : ''}`} aria-current={active ? 'page' : undefined}>
      <span className={styles.iconWrap}>
        {children}
        {count != null && count > 0 && <span className={styles.badge}>{count > 99 ? '99+' : count}</span>}
      </span>
      <span className={styles.label}>{label}</span>
    </Link>
  )
}

/**
 * Нижняя панель публичных страниц — только мобильная (<768px).
 * Четыре пункта в контексте магазина: Каталог, Избранное, Корзина, Профиль.
 */
export function PublicBottomNav() {
  const location = useLocation()
  const storeMatch = matchPath(STORE_ROUTE, location.pathname)
  const slug = storeMatch?.params.slug ?? null

  const [favoritesCount, setFavoritesCount] = useState(0)
  const [cartCountValue, setCartCountValue] = useState(0)
  const [authed, setAuthed] = useState(() => !!loadCustomerToken())

  useEffect(() => {
    if (!slug) {
      setFavoritesCount(0)
      setCartCountValue(0)
      return
    }
    function syncCounters() {
      setFavoritesCount(favoritesCountForSlug(slug!))
      setCartCountValue(cartCountForSlug(slug!))
    }
    syncCounters()
    window.addEventListener('storage', syncCounters)
    window.addEventListener('waysklad:storefront-cart', syncCounters)
    window.addEventListener(FAVORITES_EVENT, syncCounters)
    return () => {
      window.removeEventListener('storage', syncCounters)
      window.removeEventListener('waysklad:storefront-cart', syncCounters)
      window.removeEventListener(FAVORITES_EVENT, syncCounters)
    }
  }, [slug])

  useEffect(() => {
    function syncAuth() {
      setAuthed(!!loadCustomerToken())
    }
    window.addEventListener('storage', syncAuth)
    window.addEventListener('waysklad:customer-auth', syncAuth)
    return () => {
      window.removeEventListener('storage', syncAuth)
      window.removeEventListener('waysklad:customer-auth', syncAuth)
    }
  }, [])

  if (!slug) return null

  const path = location.pathname
  const accountActive =
    path === `/store/${slug}/account` ||
    path.startsWith(`/store/${slug}/account/`) ||
    path === `/store/${slug}/login`

  return (
    <nav className={styles.bar} aria-label="Основная навигация">
      <NavItem to={`/store/${slug}`} label="Каталог" active={path === `/store/${slug}`}>
        <IconLayoutGrid size={22} stroke={1.8} />
      </NavItem>

      <NavItem
        to={`/store/${slug}/favorites`}
        label="Избранное"
        active={path === `/store/${slug}/favorites`}
        count={favoritesCount}
      >
        <IconHeart size={22} stroke={1.8} />
      </NavItem>

      <NavItem
        to={`/store/${slug}/cart`}
        label="Корзина"
        active={path === `/store/${slug}/cart`}
        count={cartCountValue}
      >
        <IconShoppingCart size={22} stroke={1.8} />
      </NavItem>

      <NavItem
        to={
          authed
            ? `/store/${slug}/account`
            : `/store/${slug}/login?next=${encodeURIComponent(path + location.search)}`
        }
        label={authed ? 'Профиль' : 'Войти'}
        active={accountActive}
      >
        <IconUserCircle size={22} stroke={1.8} />
      </NavItem>
    </nav>
  )
}
