import { IconCheck } from '@tabler/icons-react'
import type { StorefrontVariant } from '../../../entities/storefront/api'
import { formatMoney } from '../../../shared/lib/format'
import type { SelectionKey } from './useSelection'
import styles from './AddonList.module.css'

interface AddonListProps {
  addons: StorefrontVariant[]
  selection: Map<SelectionKey, number>
  onToggle: (id: number, picked: boolean) => void
}

/**
 * Допы к услуге: не «выбери один вариант», а отметь нужные — их цена
 * складывается с ценой услуги. Поэтому чекбоксы, без количества.
 */
export function AddonList({ addons, selection, onToggle }: AddonListProps) {
  return (
    <ul className={styles.list}>
      {addons.map((addon) => {
        const picked = selection.has(addon.id)
        return (
          <li key={addon.id}>
            <button
              type="button"
              role="checkbox"
              aria-checked={picked}
              className={picked ? styles.itemPicked : styles.item}
              onClick={() => onToggle(addon.id, !picked)}
            >
              <span className={styles.box}>
                <IconCheck size={14} stroke={3} />
              </span>
              <span className={styles.name}>{addon.display_name}</span>
              <span className={styles.price}>+{formatMoney(addon.price ?? '0')} ₽</span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
