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
import { totalCartCount, totalFavoritesCount } from '../../shared/lib/storefrontCounters'
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
 * Корзина, заказы и каталог привязаны к конкретному магазину (общего аккаунта
 * покупателя на все магазины нет), избранное — общее для всех, /favorites.
 * Вне магазина показываем только «Избранное».
 */
export function PublicBottomNav() {
  const location = useLocation()
  const storeMatch = matchPath(STORE_ROUTE, location.pathname)
  const slug = storeMatch?.params.slug ?? null

  const [favoritesCount, setFavoritesCount] = useState(0)
  const [cartCountValue, setCartCountValue] = useState(0)
  const [authed, setAuthed] = useState(() => !!loadCustomerToken())

  useEffect(() => {
    function syncCounters() {
      setFavoritesCount(totalFavoritesCount())
      setCartCountValue(totalCartCount())
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
  }, [])

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

  const path = location.pathname
  const favoritesActive = path === '/favorites'

  return (
    <nav className={styles.bar} aria-label="Основная навигация">
      {slug && (
        <NavItem to={`/store/${slug}`} label="Каталог" active={path === `/store/${slug}`}>
          <IconLayoutGrid size={22} stroke={1.8} />
        </NavItem>
      )}

      <NavItem to="/favorites" label="Избранное" active={favoritesActive} count={favoritesCount}>
        <IconHeart size={22} stroke={1.8} />
      </NavItem>

      {slug && (
        <NavItem
          to={`/store/${slug}/cart`}
          label="Корзина"
          active={path === `/store/${slug}/cart`}
          count={cartCountValue}
        >
          <IconShoppingCart size={22} stroke={1.8} />
        </NavItem>
      )}

      {slug && (
        <NavItem
          to={
            authed
              ? `/store/${slug}/my-orders`
              : `/store/${slug}/login?next=${encodeURIComponent(path + location.search)}`
          }
          label={authed ? 'Профиль' : 'Войти'}
          active={path === `/store/${slug}/my-orders` || path === `/store/${slug}/login`}
        >
          <IconUserCircle size={22} stroke={1.8} />
        </NavItem>
      )}
    </nav>
  )
}
