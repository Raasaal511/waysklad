import { Link } from 'react-router-dom'
import styles from './Breadcrumbs.module.css'

export interface BreadcrumbItem {
  label: string
  to?: string
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[]
}

/** Общие хлебные крошки — карточка товара, каталог маркетплейса. Последний элемент —
 * не ссылка, обрезается многоточием; на мобильном лента со скроллом без переноса. */
export function Breadcrumbs({ items }: BreadcrumbsProps) {
  return (
    <nav className={styles.breadcrumbs} aria-label="Хлебные крошки">
      {items.map((item, i) => {
        const isLast = i === items.length - 1
        return (
          <span key={`${item.label}-${i}`} className={styles.breadcrumbItem}>
            {i > 0 && <span className={styles.breadcrumbSep}>›</span>}
            {isLast || !item.to ? (
              <span className={styles.breadcrumbCurrent}>{item.label}</span>
            ) : (
              <Link to={item.to} className={styles.breadcrumbLink}>
                {item.label}
              </Link>
            )}
          </span>
        )
      })}
    </nav>
  )
}
