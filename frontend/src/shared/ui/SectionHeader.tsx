import { Link } from 'react-router-dom'
import styles from './SectionHeader.module.css'

interface SectionHeaderProps {
  title: string
  /** Ссылка «Все ›» / «Смотреть все ›» — не рендерится, если не задана. */
  href?: string
  linkLabel?: string
}

/** Заголовок секции + ссылка «Все ›» — блок «Д» п.4, единый набор компонентов. */
export function SectionHeader({ title, href, linkLabel = 'Смотреть все ›' }: SectionHeaderProps) {
  return (
    <div className={styles.head}>
      <h2 className={styles.title}>{title}</h2>
      {href && (
        <Link to={href} className={styles.link}>
          {linkLabel}
        </Link>
      )}
    </div>
  )
}
