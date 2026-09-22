import { Link } from 'react-router-dom'
import { IconDiscount2, IconFlame, IconSparkles, IconStar } from '@tabler/icons-react'
import styles from './SectionChips.module.css'

const CHIPS: { key: string; label: string; icon: typeof IconDiscount2; section?: string }[] = [
  { key: 'discount', label: 'Скидки', icon: IconDiscount2, section: 'discount' },
  { key: 'new', label: 'Новинки', icon: IconSparkles, section: 'new' },
  { key: 'popular', label: 'Хиты продаж', icon: IconFlame, section: 'popular' },
  { key: 'top_rated', label: 'Высокий рейтинг', icon: IconStar, section: 'top_rated' },
]

/** Чипы-подборки под шапкой — переход в режим каталога по section=<key>. M-F2 п.1. */
export function SectionChips() {
  return (
    <nav className={styles.row} aria-label="Быстрые подборки">
      {CHIPS.map((chip) => (
        <Link key={chip.key} to={`/marketplace?section=${chip.section}`} className={styles.chip}>
          <span className={styles.iconWrap}>
            <chip.icon size={16} stroke={1.8} />
          </span>
          {chip.label}
        </Link>
      ))}
    </nav>
  )
}
