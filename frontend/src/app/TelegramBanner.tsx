import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { IconBrandTelegram, IconX } from '@tabler/icons-react'
import { useAuth } from './AuthContext'
import { useShop } from './ShopContext'
import styles from './TelegramBanner.module.css'

const DISMISS_KEY = 'waysklad:telegram-banner-dismissed'

/**
 * Владелец, зарегистрированный до бота: заявки и сводки никуда не уходят,
 * пока не подключён Telegram. Мягкое напоминание — работать не мешает,
 * закрывается до конца сессии.
 */
export function TelegramBanner() {
  const { user } = useAuth()
  const { shop } = useShop()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [dismissed, setDismissed] = useState(() => {
    try {
      return sessionStorage.getItem(DISMISS_KEY) === '1'
    } catch {
      return false
    }
  })

  if (user?.role !== 'owner' || !shop || shop.owner_telegram_chat_id || dismissed) return null
  if (pathname.startsWith('/profile') || pathname.startsWith('/sales/new')) return null

  function dismiss() {
    setDismissed(true)
    try {
      sessionStorage.setItem(DISMISS_KEY, '1')
    } catch {
      /* закроется только до перезагрузки */
    }
  }

  return (
    <div className={styles.banner} role="status">
      <IconBrandTelegram size={22} stroke={1.8} className={styles.icon} aria-hidden="true" />
      <span className={styles.text}>Подключите Telegram — туда придут заявки и сводка</span>
      <button type="button" className={styles.action} onClick={() => navigate('/profile?tab=connections')}>
        Подключить
      </button>
      <button type="button" className={styles.close} onClick={dismiss} aria-label="Скрыть до следующего входа">
        <IconX size={18} stroke={1.8} />
      </button>
    </div>
  )
}
