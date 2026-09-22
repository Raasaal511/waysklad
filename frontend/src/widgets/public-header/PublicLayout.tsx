import { useEffect, type ReactNode } from 'react'
import { matchPath, useLocation } from 'react-router-dom'
import { saveLastStoreSlug } from '../../shared/lib/lastStore'
import { PublicHeader } from './PublicHeader'
import { PublicFooter } from './PublicFooter'
import { PublicBottomNav } from './PublicBottomNav'
import styles from './PublicLayout.module.css'

const STORE_ROUTE = '/store/:slug/*'

/**
 * Общий каркас публичных страниц магазина: шапка + контейнер + подвал,
 * на мобильном — нижняя навигация.
 */
export function PublicLayout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const storeMatch = matchPath(STORE_ROUTE, location.pathname)
  const slug = storeMatch?.params.slug

  useEffect(() => {
    if (slug) saveLastStoreSlug(slug)
  }, [slug])

  return (
    <div className={styles.page}>
      <PublicHeader />
      <main className={styles.main}>{children}</main>
      <PublicFooter />
      <PublicBottomNav />
    </div>
  )
}
