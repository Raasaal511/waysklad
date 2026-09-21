import { Link } from 'react-router-dom'
import { FOOTER_COLUMNS } from '../../shared/config'
import styles from './PublicFooter.module.css'

export function PublicFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        {/* FOOTER_COLUMNS сейчас пуст (все пункты вели на отключённый маркетплейс) —
            без этой проверки остаётся пустая сетка с лишними отступами */}
        {FOOTER_COLUMNS.length > 0 && (
        <div className={styles.columns}>
          {FOOTER_COLUMNS.map((col) => (
            <div key={col.title} className={styles.column}>
              <h2 className={styles.columnTitle}>{col.title}</h2>
              <ul className={styles.linkList}>
                {col.links.map((link) => (
                  <li key={link.label}>
                    <Link to={link.href} className={styles.link}>
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        )}
        <p className={styles.copyright}>© 2026 ВайСклад · Товарный учёт и витрина для малого бизнеса</p>
      </div>
    </footer>
  )
}
