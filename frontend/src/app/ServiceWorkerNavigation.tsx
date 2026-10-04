import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

/**
 * Касание уведомления при уже открытом кабинете: service worker (public/push-sw.js)
 * присылает ссылку сюда, и переход идёт внутри приложения — без перезагрузки,
 * недописанная продажа на экране не теряется.
 */
export function ServiceWorkerNavigation() {
  const navigate = useNavigate()

  useEffect(() => {
    if (!('serviceWorker' in navigator)) return
    const onMessage = (event: MessageEvent) => {
      const data = event.data as { type?: string; link?: unknown } | null
      if (data?.type !== 'waysklad:navigate' || typeof data.link !== 'string') return
      if (!data.link.startsWith('/') || data.link.startsWith('//')) return
      navigate(data.link)
    }
    navigator.serviceWorker.addEventListener('message', onMessage)
    return () => navigator.serviceWorker.removeEventListener('message', onMessage)
  }, [navigate])

  return null
}
