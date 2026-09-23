import { useEffect, useState } from 'react'
import { Link, matchPath, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import {
  IconHeart,
  IconSearch,
  IconShoppingCart,
  IconUserCircle,
  IconX,
} from '@tabler/icons-react'
import {
  getStorefrontShopProfileCached,
  peekCachedStorefrontShopProfile,
} from '../../entities/storefront/api'
import { loadCustomerToken } from '../../entities/auth/customerApi'
import { cartCountForSlug, favoritesCountForSlug } from '../../shared/lib/storefrontCounters'
import { FAVORITES_EVENT } from '../../shared/lib/favorites'
import styles from './PublicHeader.module.css'

const STORE_ROUTE = '/store/:slug/*'

/** Счётчик с кружком: не рендерится вовсе при 0 (п.1 блока «Д» шага P1). */
function CountBadge({ count }: { count: number }) {
  if (count <= 0) return null
  return <span className={styles.badge}>{count > 99 ? '99+' : count}</span>
}

/**
 * Единая шапка публичных страниц в контексте магазина:
 * логотип и название → каталог, поиск по магазину, избранное, корзина, профиль/вход.
 */
export function PublicHeader() {
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const storeMatch = matchPath(STORE_ROUTE, location.pathname)
  const slug = storeMatch?.params.slug ?? null

  const [shopName, setShopName] = useState<string | null>(null)
  const [shopLogo, setShopLogo] = useState<string>('')
  const [scrolled, setScrolled] = useState(false)
  const [favoritesCount, setFavoritesCount] = useState(0)
  const [cartCountValue, setCartCountValue] = useState(0)
  const [authed, setAuthed] = useState(() => !!loadCustomerToken())
  const [query, setQuery] = useState(searchParams.get('q') ?? '')

  useEffect(() => {
    setQuery(searchParams.get('q') ?? '')
  }, [searchParams])

  useEffect(() => {
    if (!slug) {
      setShopName(null)
      setShopLogo('')
      return
    }
    const cached = peekCachedStorefrontShopProfile(slug)
    if (cached) {
      setShopName(cached.name)
      setShopLogo(cached.logo)
      return
    }
    let cancelled = false
    getStorefrontShopProfileCached(slug)
      .then((profile) => {
        if (!cancelled) {
          setShopName(profile.name)
          setShopLogo(profile.logo)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setShopName(null)
          setShopLogo('')
        }
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

  function submitSearch(value: string) {
    if (!slug) return
    const next = new URLSearchParams()
    if (value.trim()) next.set('q', value.trim())
    // поиск всегда по каталогу текущего магазина, не по карточке/корзине
    navigate({ pathname: `/store/${slug}`, search: next.toString() }, { replace: true })
  }

  const searchPlaceholder = shopName
    ? `Искать в магазине «${shopName}»`
    : 'Искать в магазине…'
  const catalogTo = slug ? `/store/${slug}` : '/'
  const accountTo = authed
    ? '/account'
    : slug
      ? `/store/${slug}/login?next=${encodeURIComponent('/account')}`
      : '/account'

  return (
    <header className={`${styles.header} ${scrolled ? styles.headerScrolled : ''}`}>
      <div className={styles.row}>
        {slug ? (
          <Link to={catalogTo} className={styles.brand} aria-label={shopName ?? 'Каталог магазина'}>
            {shopLogo ? (
              <img src={shopLogo} alt="" width={32} height={32} className={styles.logoMark} />
            ) : (
              <span className={styles.logoFallback} aria-hidden="true">
                {(shopName ?? '?').charAt(0).toUpperCase()}
              </span>
            )}
            <span className={styles.brandName}>{shopName ?? '…'}</span>
          </Link>
        ) : (
          <div className={styles.brand}>
            <span className={styles.brandName}>ВайСклад</span>
          </div>
        )}

        {slug && (
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
        )}

        {(slug || authed || location.pathname.startsWith('/account')) && (
          <div className={styles.actions}>
            {slug && (
              <>
                <Link
                  to={`/store/${slug}/favorites`}
                  className={styles.iconAction}
                  aria-label="Избранное"
                >
                  <IconHeart size={22} stroke={1.8} />
                  <CountBadge count={favoritesCount} />
                </Link>
                <Link to={`/store/${slug}/cart`} className={styles.iconAction} aria-label="Корзина">
                  <IconShoppingCart size={22} stroke={1.8} />
                  <CountBadge count={cartCountValue} />
                </Link>
              </>
            )}
            {authed ? (
              <Link to={accountTo} className={styles.iconAction} aria-label="Профиль">
                <IconUserCircle size={22} stroke={1.8} />
              </Link>
            ) : (
              <Link to={accountTo} className={styles.loginBtn}>
                Войти
              </Link>
            )}
          </div>
        )}
      </div>

      {slug && (
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
      )}
    </header>
  )
}
