import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { IconArrowBackUp, IconSettings } from '@tabler/icons-react'
import { useAuth } from '../../app/AuthContext'
import { getShop } from '../../entities/profile/api'
import styles from './OwnerStorefrontBar.module.css'

/** Полоска «вы смотрите свою витрину» с переходом в кабинет.
 *
 * Владелец часто открывает свою витрину, чтобы посмотреть её глазами
 * покупателя, и обратной дороги в кабинет не было — приходилось править URL
 * руками. Показываем полоску только тому, чей это магазин.
 *
 * Принадлежность витрины проверяется на сервере, а не по URL: slug берётся
 * из GET /auth/shop, то есть из токена текущего пользователя. Подставить
 * чужой slug в адрес и получить ссылку в чужой склад нельзя — сравнение идёт
 * с тем магазином, к которому привязан сам токен. Сама ссылка тоже ничего не
 * открывает без прав: /stock под RequireAuth, а данные кабинета отдаются
 * строго по tenant_id из токена.
 */
export function OwnerStorefrontBar({ slug }: { slug: string }) {
  const { user } = useAuth()
  const [ownSlug, setOwnSlug] = useState<string | null>(null)

  // сотрудники (продавец, кладовщик) витриной не управляют — полоска только владельцу
  const isOwner = user?.role === 'owner'

  useEffect(() => {
    if (!isOwner) {
      setOwnSlug(null)
      return
    }
    let cancelled = false
    getShop()
      .then((shop) => {
        if (!cancelled) setOwnSlug(shop.slug)
      })
      .catch(() => {
        // не авторизован или сеть недоступна — просто не показываем полоску
        if (!cancelled) setOwnSlug(null)
      })
    return () => {
      cancelled = true
    }
  }, [isOwner])

  if (!isOwner || !ownSlug || ownSlug !== slug) return null

  return (
    <div className={styles.bar}>
      <span className={styles.label}>Это ваша витрина — покупатели видят её так</span>
      <div className={styles.actions}>
        <Link to="/storefront" className={styles.action}>
          <IconSettings size={16} stroke={1.8} aria-hidden="true" />
          Настроить
        </Link>
        <Link to="/stock" className={`${styles.action} ${styles.actionPrimary}`}>
          <IconArrowBackUp size={16} stroke={1.8} aria-hidden="true" />
          В склад
        </Link>
      </div>
    </div>
  )
}
