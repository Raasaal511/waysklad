import { useEffect, useState } from 'react'
import { Link, matchPath, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import {
  IconChevronLeft,
  IconHeart,
  IconSearch,
  IconShoppingCart,
  IconUserCircle,
  IconX,
} from '@tabler/icons-react'
import { getStorefrontShopProfileCached, peekCachedStorefrontShopProfile } from '../../entities/storefront/api'
import { loadCustomerToken } from '../../entities/auth/customerApi'
import { useTheme } from '../../app/ThemeContext'
import { totalCartCount, totalFavoritesCount } from '../../shared/lib/storefrontCounters'
import { FAVORITES_EVENT } from '../../shared/lib/favorites'
import { CustomerLoginModal, notifyCustomerAuthChanged } from '../../pages/storefront/CustomerLoginModal'
import styles from './PublicHeader.module.css'

const STORE_ROUTE = '/store/:slug/*'

/** Счётчик с кружком: не рендерится вовсе при 0 (п.1 блока «Д» шага P1). */
function CountBadge({ count }: { count: number }) {
  if (count <= 0) return null
  return <span className={styles.badge}>{count > 99 ? '99+' : count}</span>
}

export function PublicHeader() {
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { mode } = useTheme()

  const storeMatch = matchPath(STORE_ROUTE, location.pathname)
  const slug = storeMatch?.params.slug ?? null

  const [shopName, setShopName] = useState<string | null>(null)
  const [scrolled, setScrolled] = useState(false)
  const [favoritesCount, setFavoritesCount] = useState(0)
  const [cartCountValue, setCartCountValue] = useState(0)
  const [authed, setAuthed] = useState(() => !!loadCustomerToken())
  const [showLogin, setShowLogin] = useState(false)
  const [query, setQuery] = useState(searchParams.get('q') ?? '')

  useEffect(() => {
    setQuery(searchParams.get('q') ?? '')
  }, [searchParams])

  // название магазина — для плейсхолдера поиска «Искать в магазине «...»»;
  // шапка не имеет доступа к данным, загруженным внутри страницы каталога/товара,
  // но берёт профиль из общего кэша (getStorefrontShopProfileCached) — та же страница
  // почти всегда уже запросила тот же профиль, второй поход на сервер не нужен (P7 п.2)
  useEffect(() => {
    if (!slug) {
      setShopName(null)
      return
    }
    const cached = peekCachedStorefrontShopProfile(slug)
    if (cached) {
      setShopName(cached.name)
      return
    }
    let cancelled = false
    getStorefrontShopProfileCached(slug)
      .then((profile) => {
        if (!cancelled) setShopName(profile.name)
      })
      .catch(() => {
        if (!cancelled) setShopName(null)
      })
    return () => {
      cancelled = true
    }
  }, [slug])

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 8)
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

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

  function submitSearch(value: string) {
    const next = new URLSearchParams(searchParams)
    if (value.trim()) next.set('q', value.trim())
    else next.delete('q')
    navigate({ pathname: location.pathname, search: next.toString() }, { replace: true })
  }

  const logoSrc = mode === 'dark' ? '/logo-mark-dark.png' : '/logo-mark.png'
  const searchPlaceholder = slug
    ? `Искать в магазине «${shopName ?? '…'}»`
    : 'Искать товары и магазины…'

  return (
    <header className={`${styles.header} ${scrolled ? styles.headerScrolled : ''}`}>
      <div className={styles.row}>
        {slug && (
          <Link to={`/store/${slug}`} className={styles.backBtn} aria-label="Назад в каталог магазина">
            <IconChevronLeft size={22} stroke={1.8} />
          </Link>
        )}

        {/* не ссылка: общая витрина всех магазинов отключена, вести логотипу
            некуда — покупатель всегда внутри конкретного магазина */}
        <div className={styles.brand}>
          <img src={logoSrc} alt="" width={32} height={32} className={styles.logoMark} />
          <span className={styles.brandName}>ВайСклад</span>
        </div>

        <form
          className={styles.searchDesktop}
          role="search"
          onSubmit={(e) => {
            e.preventDefault()
            submitSearch(query)
          }}
        >
          <IconSearch size={20} stroke={1.8} className={styles.searchIcon} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
          />
          {query && (
            <button
              type="button"
              className={styles.searchClear}
              onClick={() => {
                setQuery('')
                submitSearch('')
              }}
              aria-label="Очистить поиск"
            >
              <IconX size={16} stroke={2} />
            </button>
          )}
        </form>

        <div className={styles.actions}>
          {/* избранное общее для всех магазинов — отдельная страница /favorites,
              счётчик тоже суммарный (см. shared/lib/favorites.ts) */}
          <Link to="/favorites" className={styles.iconAction} aria-label="Избранное">
            <IconHeart size={22} stroke={1.8} />
            <CountBadge count={favoritesCount} />
          </Link>
          {slug ? (
            <Link to={`/store/${slug}/cart`} className={styles.iconAction} aria-label="Корзина">
              <IconShoppingCart size={22} stroke={1.8} />
              <CountBadge count={cartCountValue} />
            </Link>
          ) : (
            <span className={styles.iconAction} aria-disabled="true" title="Откройте магазин, чтобы посмотреть корзину">
              <IconShoppingCart size={22} stroke={1.8} />
              <CountBadge count={cartCountValue} />
            </span>
          )}
          {authed && slug ? (
            <Link to={`/store/${slug}/my-orders`} className={styles.iconAction} aria-label="Мои заказы">
              <IconUserCircle size={22} stroke={1.8} />
            </Link>
          ) : authed ? (
            // авторизован, но вне магазина — «Мои заказы» привязаны к конкретному
            // магазину (нет общего аккаунта покупателя на все магазины), поэтому
            // просто индикатор без действия
            <span className={styles.iconAction} aria-disabled="true" title="Откройте магазин, чтобы посмотреть заказы">
              <IconUserCircle size={22} stroke={1.8} />
            </span>
          ) : slug ? (
            // отдельная страница входа/регистрации; next возвращает туда, откуда пришли.
            // Модалка остаётся для входа по ходу действия (корзина, отзыв).
            <Link
              to={`/store/${slug}/login?next=${encodeURIComponent(location.pathname + location.search)}`}
              className={styles.loginBtn}
            >
              Войти
            </Link>
          ) : (
            <button type="button" className={styles.loginBtn} onClick={() => setShowLogin(true)}>
              Войти
            </button>
          )}
        </div>
      </div>

      <form
        className={styles.searchMobile}
        role="search"
        onSubmit={(e) => {
          e.preventDefault()
          submitSearch(query)
        }}
      >
        <IconSearch size={18} stroke={1.8} className={styles.searchIcon} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={searchPlaceholder}
          aria-label={searchPlaceholder}
        />
      </form>

      {showLogin && (
        <CustomerLoginModal
          onClose={() => setShowLogin(false)}
          onSuccess={() => {
            notifyCustomerAuthChanged()
            setShowLogin(false)
          }}
        />
      )}
    </header>
  )
}
