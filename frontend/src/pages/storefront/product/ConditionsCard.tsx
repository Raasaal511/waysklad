import { useState } from 'react'
import { IconMapPin, IconCash, IconChevronRight, IconExternalLink } from '@tabler/icons-react'
import { Modal } from '../../../shared/ui/Modal'
import type { StorefrontProfileAddress } from '../../../entities/storefront/api'
import pageStyles from './ProductPage.module.css'
import styles from './ProductAside.module.css'

interface ConditionsCardProps {
  addresses: StorefrontProfileAddress[]
  paymentPolicy: string | null
}

/** Условия получения: адрес(а) магазина и оплата при получении. */
export function ConditionsCard({ addresses, paymentPolicy }: ConditionsCardProps) {
  const [addressOpen, setAddressOpen] = useState(false)
  const [paymentOpen, setPaymentOpen] = useState(false)

  if (addresses.length === 0 && !paymentPolicy) return null

  const firstAddress = addresses[0]
  const extraCount = addresses.length - 1

  return (
    <div className={pageStyles.card}>
      {addresses.length > 0 && (
        <button type="button" className={styles.conditionsRow} onClick={() => setAddressOpen(true)}>
          <IconMapPin size={20} stroke={1.8} className={styles.conditionsIcon} />
          <div className={styles.conditionsBody}>
            <p className={styles.conditionsTitle}>Адрес магазина</p>
            <p className={styles.conditionsSub}>
              {firstAddress.address || firstAddress.name}
              {extraCount > 0 ? ` · + ещё ${extraCount}` : ''}
            </p>
          </div>
          <IconChevronRight size={16} stroke={1.8} className={styles.conditionsChevron} />
        </button>
      )}
      <button
        type="button"
        className={styles.conditionsRow}
        onClick={() => paymentPolicy && setPaymentOpen(true)}
      >
        <IconCash size={20} stroke={1.8} className={styles.conditionsIcon} />
        <div className={styles.conditionsBody}>
          <p className={styles.conditionsTitle}>Оплата при получении</p>
          <p className={styles.conditionsSub}>Онлайн-оплаты нет — платите магазину при получении</p>
        </div>
        {paymentPolicy && <IconChevronRight size={16} stroke={1.8} className={styles.conditionsChevron} />}
      </button>

      {addressOpen && (
        <Modal title="Адреса магазина" onClose={() => setAddressOpen(false)}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {addresses.map((a, i) => (
              <div key={`${a.name}-${i}`}>
                <p style={{ fontWeight: 600, margin: '0 0 2px' }}>{a.name}</p>
                <p style={{ margin: '0 0 6px', color: 'var(--text-muted)' }}>{a.address}</p>
                {a.address && (
                  <a
                    href={`https://yandex.ru/maps/?text=${encodeURIComponent(a.address)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--accent)', fontSize: 14 }}
                  >
                    <IconExternalLink size={14} stroke={1.8} /> Открыть в Яндекс Картах
                  </a>
                )}
              </div>
            ))}
          </div>
        </Modal>
      )}

      {paymentOpen && paymentPolicy && (
        <Modal title="Оплата" onClose={() => setPaymentOpen(false)}>
          <p style={{ whiteSpace: 'pre-line', margin: 0 }}>{paymentPolicy}</p>
        </Modal>
      )}
    </div>
  )
}
