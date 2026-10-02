/* Web Push внутри service worker (подключается через workbox.importScripts в
 * vite.config.ts). Сервер присылает {title, body, link, tag} — см.
 * backend/app/infrastructure/notifications/web_push.py. */

self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    data = { body: event.data ? event.data.text() : '' }
  }
  const tag = typeof data.tag === 'string' && data.tag ? data.tag : undefined
  // Показываем всегда, даже при открытом кабинете: Safari отзывает подписку
  // после нескольких «тихих» push, а Chrome сам рисует «сайт обновлён в фоне».
  event.waitUntil(
    self.registration.showNotification(data.title || 'WaySklad', {
      body: data.body || '',
      icon: '/pwa-192.png',
      badge: '/push-badge.png',
      lang: 'ru',
      tag,
      // новое сообщение по той же заявке заменяет старое — но звенит снова
      renotify: Boolean(tag),
      data: { link: safeLink(data.link) },
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const link = safeLink(event.notification.data && event.notification.data.link)
  event.waitUntil(openLink(link))
})

/** Только путь внутри кабинета: уведомление не должно уводить на чужой сайт. */
function safeLink(link) {
  return typeof link === 'string' && link.startsWith('/') && !link.startsWith('//') ? link : '/'
}

async function openLink(link) {
  const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
  const open = windows.find((client) => new URL(client.url).origin === self.location.origin)
  if (open) {
    // Открытый кабинет переходит сам (useServiceWorkerNavigation) — без
    // перезагрузки, недописанная продажа на экране не теряется.
    open.postMessage({ type: 'waysklad:navigate', link })
    return open.focus()
  }
  return self.clients.openWindow(link)
}
