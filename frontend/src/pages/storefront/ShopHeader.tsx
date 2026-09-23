import { useState } from 'react'
import {
  IconBrandTelegram,
  IconBrandWhatsapp,
  IconMapPin,
  IconMessage,
  IconPhone,
} from '@tabler/icons-react'
import type { StorefrontShopProfile } from '../../entities/storefront/api'
import { plural } from '../../shared/lib/format'
import { formatMonthYearGenitive } from './product/productUtils'
import { Button } from '../../shared/ui/Button'
import { InlinePopover } from '../../shared/ui/InlinePopover'
import { Modal } from '../../shared/ui/Modal'
import { ExpandableText } from '../../shared/ui/ExpandableText'
import styles from './ShopHeader.module.css'

const POLICY_LABELS: { key: keyof StorefrontShopProfile['policies']; title: string }[] = [
  { key: 'payment', title: 'Оплата' },
  { key: 'delivery', title: 'Доставка' },
  { key: 'returns', title: 'Возврат товара' },
  { key: 'refund_money', title: 'Возврат денег' },
]

interface ShopHeaderProps {
  profile: StorefrontShopProfile
}

/** Шапка магазина в каталоге — переиспользуется на карточке товара (карточка продавца). Блок «Д», шаг P3 п.1. */
export function ShopHeader({ profile }: ShopHeaderProps) {
  const [contactsOpen, setContactsOpen] = useState(false)
  const [conditionsOpen, setConditionsOpen] = useState(false)

  const hasReviews = profile.rating.reviews_count > 0
  const hasContacts = !!(profile.contacts.phone || profile.contacts.whatsapp || profile.contacts.telegram)
  const policies = POLICY_LABELS.filter((p) => profile.policies[p.key] != null)
  const hasConditions = profile.addresses.length > 0 || policies.length > 0

  return (
    <div className={styles.card}>
      <div className={styles.main}>
        {profile.logo ? (
          <img src={profile.logo} alt={profile.name} width={72} height={72} className={styles.logo} />
        ) : (
          <div className={styles.logoFallback} aria-hidden="true">
            {profile.name.charAt(0).toUpperCase()}
          </div>
        )}

        <div className={styles.info}>
          <h1 className={styles.name}>{profile.name}</h1>

          <p className={styles.meta}>
            {hasReviews ? (
              <span className={styles.metaItem}>
                <span className={styles.ratingStar}>★ {profile.rating.average_rating.toFixed(1)}</span>
                {' · '}
                {profile.rating.reviews_count} {plural(profile.rating.reviews_count, ['отзыв', 'отзыва', 'отзывов'])}
              </span>
            ) : (
              <span className={styles.metaItem}>Новый магазин</span>
            )}
            <span className={styles.metaItem}>
              {profile.products_count} {plural(profile.products_count, ['товар', 'товара', 'товаров'])}
            </span>
            {profile.on_platform_since && (
              <span className={styles.metaItem}>С {formatMonthYearGenitive(profile.on_platform_since)}</span>
            )}
          </p>

          {profile.description && (
            <ExpandableText text={profile.description} titleAs="h2" clampLines={2} />
          )}
        </div>

        <div className={styles.actions}>
          {hasContacts && (
            <InlinePopover
              title="Связаться с магазином"
              open={contactsOpen}
              onOpenChange={setContactsOpen}
              trigger={
                <Button variant="secondary" onClick={() => setContactsOpen((v) => !v)}>
                  <IconMessage size={18} stroke={1.8} /> Написать
                </Button>
              }
            >
              <div className={styles.contactList}>
                {profile.contacts.whatsapp && (
                  <a
                    className={styles.contactItem}
                    href={`https://wa.me/${profile.contacts.whatsapp.replace(/\D/g, '')}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <IconBrandWhatsapp size={18} stroke={1.8} /> WhatsApp
                  </a>
                )}
                {profile.contacts.telegram && (
                  <a
                    className={styles.contactItem}
                    href={`https://t.me/${profile.contacts.telegram.replace(/^@/, '')}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <IconBrandTelegram size={18} stroke={1.8} /> Telegram
                  </a>
                )}
                {profile.contacts.phone && (
                  <a className={styles.contactItem} href={`tel:${profile.contacts.phone}`}>
                    <IconPhone size={18} stroke={1.8} /> {profile.contacts.phone}
                  </a>
                )}
              </div>
            </InlinePopover>
          )}
          {hasConditions && (
            <Button variant="secondary" onClick={() => setConditionsOpen(true)}>
              <IconMapPin size={18} stroke={1.8} /> Адрес и условия
            </Button>
          )}
        </div>
      </div>

      {conditionsOpen && (
        <Modal title="Адрес и условия" onClose={() => setConditionsOpen(false)}>
          <div className={styles.conditionsBody}>
            {profile.addresses.length > 0 && (
              <section>
                <h3 className={styles.conditionsTitle}>Адреса</h3>
                <div className={styles.addressList}>
                  {profile.addresses.map((a, i) => (
                    <div key={`${a.name}-${i}`} className={styles.addressItem}>
                      <p className={styles.addressName}>{a.name}</p>
                      <p className={styles.addressValue}>{a.address}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}
            {policies.map((p) => (
              <section key={p.key}>
                <h3 className={styles.conditionsTitle}>{p.title}</h3>
                <p className={styles.policyText}>{profile.policies[p.key]}</p>
              </section>
            ))}
          </div>
        </Modal>
      )}
    </div>
  )
}

/** Skeleton той же геометрии, что ShopHeader — состояние загрузки каталога.
 *  Строка кнопок (.actions) зарезервирована на случай самого частого исхода —
 *  у магазина есть контакты — чтобы переход в контент не двигал макет (CLS). */
export function ShopHeaderSkeleton() {
  return (
    <div className={styles.card} aria-hidden="true">
      <div className={styles.main}>
        <div className={`${styles.logo} ${styles.skeletonLogo}`} />
        <div className={styles.info}>
          <div className={`${styles.skeletonLine} ${styles.skeletonTitle}`} />
          <div className={`${styles.skeletonLine} ${styles.skeletonMeta}`} />
          <div className={`${styles.skeletonLine} ${styles.skeletonText}`} />
        </div>
        <div className={styles.actions}>
          <div className={`${styles.skeletonLine} ${styles.skeletonActionBtn}`} />
          <div className={`${styles.skeletonLine} ${styles.skeletonActionBtn}`} />
        </div>
      </div>
    </div>
  )
}
