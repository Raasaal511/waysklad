import { IconMessageCircle, IconCheck } from '@tabler/icons-react'
import { Button } from '../../../shared/ui/Button'
import { formatMoney } from '../../../shared/lib/format'
import styles from './MobileDock.module.css'

interface MobileDockProps {
  total: number
  hasSelection: boolean
  inStock: boolean
  added: boolean
  onAdd: () => void
  hasContacts: boolean
}

/** Мобильный dock — показывается, когда TotalCard ушёл из вьюпорта. Кнопка «Написать»
 *  прокручивает к TotalCard, где уже реализовано меню контактов — логика не дублируется. */
export function MobileDock({ total, hasSelection, inStock, added, onAdd, hasContacts }: MobileDockProps) {
  function scrollToContact() {
    document.getElementById('product-total-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
  return (
    <div className={styles.dock}>
      <div className={styles.totalBlock}>
        <p className={styles.totalLabel}>Итого</p>
        <p className={styles.totalValue}>{hasSelection ? `${formatMoney(total.toFixed(2))} ₽` : '—'}</p>
      </div>
      <div className={styles.actions}>
        {hasContacts && (
          <button type="button" className={styles.contactBtn} onClick={scrollToContact} aria-label="Написать магазину">
            <IconMessageCircle size={20} stroke={1.8} />
          </button>
        )}
        <Button className={styles.addBtn} onClick={onAdd} disabled={!inStock}>
          {!inStock ? (
            'Нет в наличии'
          ) : added ? (
            <>
              <IconCheck size={16} stroke={2} /> Добавлено
            </>
          ) : (
            'В корзину'
          )}
        </Button>
      </div>
    </div>
  )
}
