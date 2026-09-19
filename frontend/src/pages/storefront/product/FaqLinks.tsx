import { useState } from 'react'
import { Modal } from '../../../shared/ui/Modal'
import type { StorefrontProfilePolicies } from '../../../entities/storefront/api'
import pageStyles from './ProductPage.module.css'
import styles from './ProductAside.module.css'

interface FaqLinksProps {
  policies: StorefrontProfilePolicies
}

const FAQ_ITEMS: { key: keyof StorefrontProfilePolicies; label: string }[] = [
  { key: 'refund_money', label: 'Возврат денег' },
  { key: 'payment', label: 'Способы оплаты' },
  { key: 'delivery', label: 'Условия доставки' },
  { key: 'returns', label: 'Возврат товаров' },
]

/** «Часто задаваемые вопросы» — только пункты с заполненным текстом, открываются в модалке. */
export function FaqLinks({ policies }: FaqLinksProps) {
  const [openKey, setOpenKey] = useState<keyof StorefrontProfilePolicies | null>(null)

  const items = FAQ_ITEMS.filter((item) => policies[item.key])
  if (items.length === 0) return null

  const openItem = items.find((i) => i.key === openKey)

  return (
    <div className={pageStyles.card}>
      <h2 className={styles.faqTitle}>Часто задаваемые вопросы</h2>
      <div className={styles.faqGrid}>
        {items.map((item) => (
          <button key={item.key} type="button" className={styles.faqLink} onClick={() => setOpenKey(item.key)}>
            {item.label}
          </button>
        ))}
      </div>

      {openItem && (
        <Modal title={openItem.label} onClose={() => setOpenKey(null)}>
          <p style={{ whiteSpace: 'pre-line', margin: 0 }}>{policies[openItem.key]}</p>
        </Modal>
      )}
    </div>
  )
}
