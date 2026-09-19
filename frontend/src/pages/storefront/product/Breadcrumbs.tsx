import { Link } from 'react-router-dom'
import type { StorefrontProductCategory } from '../../../entities/storefront/api'
import styles from './ProductPage.module.css'

interface BreadcrumbsProps {
  slug: string
  category: StorefrontProductCategory | null
}

/** «Каталог › <родитель> › <категория>» — ссылки ведут в каталог магазина с выбранной категорией. */
export function Breadcrumbs({ slug, category }: BreadcrumbsProps) {
  const items: { label: string; to?: string }[] = [{ label: 'Каталог', to: `/store/${slug}` }]
  if (category?.parent) {
    items.push({ label: category.parent.name, to: `/store/${slug}?category_id=${category.parent.id}` })
  }
  if (category) {
    items.push({ label: category.name, to: `/store/${slug}?category_id=${category.id}` })
  }

  return (
    <nav className={styles.breadcrumbs} aria-label="Хлебные крошки">
      {items.map((item, i) => {
        const isLast = i === items.length - 1
        return (
          <span key={`${item.label}-${i}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
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
