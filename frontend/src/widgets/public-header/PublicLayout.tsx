import type { ReactNode } from 'react'
import { PublicHeader } from './PublicHeader'
import { PublicFooter } from './PublicFooter'
import styles from './PublicLayout.module.css'

/**
 * Общий каркас публичных страниц: шапка + контейнер 1280px + подвал.
 * Применяется к /marketplace, /store/:slug, /store/:slug/products/:id,
 * /store/:slug/cart.
 */
export function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className={styles.page}>
      <PublicHeader />
      <main className={styles.main}>{children}</main>
      <PublicFooter />
    </div>
  )
}
