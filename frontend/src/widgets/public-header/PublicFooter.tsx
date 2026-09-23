import { useEffect, useState } from 'react'
import { Link, matchPath, useLocation } from 'react-router-dom'
import {
  getStorefrontShopProfileCached,
  peekCachedStorefrontShopProfile,
  type StorefrontShopProfile,
} from '../../entities/storefront/api'
import styles from './PublicFooter.module.css'

const STORE_ROUTE = '/store/:slug/*'

/**
 * Подвал магазина: контакты, ссылка на каталог, «Работает на ВайСклад».
 * Без разделов «Покупателям / Продавцам / О платформе».
 */
export function PublicFooter() {
  const location = useLocation()
  const storeMatch = matchPath(STORE_ROUTE, location.pathname)
  const slug = storeMatch?.params.slug ?? null

  const [profile, setProfile] = useState<StorefrontShopProfile | null>(() =>
    slug ? peekCachedStorefrontShopProfile(slug) : null,
  )

  useEffect(() => {
    if (!slug) {
      setProfile(null)
      return
    }
    const cached = peekCachedStorefrontShopProfile(slug)
    if (cached) {
      setProfile(cached)
      return
    }
    let cancelled = false
    getStorefrontShopProfileCached(slug)
      .then((p) => {
        if (!cancelled) setProfile(p)
      })
      .catch(() => {
        if (!cancelled) setProfile(null)
      })
    return () => {
      cancelled = true
    }
  }, [slug])

  const phone = profile?.contacts.phone?.trim() || ''
  const whatsapp = profile?.contacts.whatsapp?.trim() || ''
  const telegram = profile?.contacts.telegram?.trim() || ''
  const hasContacts = !!(phone || whatsapp || telegram)

  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        {slug && (
          <div className={styles.shopBlock}>
            {profile?.name && <p className={styles.shopName}>{profile.name}</p>}
            <Link to={`/store/${slug}`} className={styles.link}>
              Каталог магазина
            </Link>
            {hasContacts && (
              <ul className={styles.contactList}>
                {phone && (
                  <li>
                    <a href={`tel:${phone.replace(/\s/g, '')}`} className={styles.link}>
                      {phone}
                    </a>
                  </li>
                )}
                {whatsapp && (
                  <li>
                    <a
                      href={`https://wa.me/${whatsapp.replace(/\D/g, '')}`}
                      className={styles.link}
                      target="_blank"
                      rel="noreferrer"
                    >
                      WhatsApp
                    </a>
                  </li>
                )}
                {telegram && (
                  <li>
                    <a
                      href={
                        telegram.startsWith('http')
                          ? telegram
                          : `https://t.me/${telegram.replace(/^@/, '')}`
                      }
                      className={styles.link}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Telegram
                    </a>
                  </li>
                )}
              </ul>
            )}
          </div>
        )}
        <p className={styles.copyright}>Работает на ВайСклад</p>
      </div>
    </footer>
  )
}
