import type { ReactNode } from 'react'
import { PublicHeader } from './PublicHeader'
import { PublicFooter } from './PublicFooter'
import { PublicBottomNav } from './PublicBottomNav'
import styles from './PublicLayout.module.css'

/**
 * Общий каркас публичных страниц: шапка + контейнер 1280px + подвал,
 * на мобильном — ещё и нижняя навигация.
 * Применяется к /store/:slug, /store/:slug/products/:id, /store/:slug/cart,
 * /favorites и к заглушке /marketplace.
 */
export function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className={styles.page}>
      <PublicHeader />
      <main className={styles.main}>{children}</main>
      <PublicFooter />
      <PublicBottomNav />
    </div>
  )
}
