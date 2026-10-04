import {
  deletePushSubscription,
  getPushKey,
  savePushSubscription,
  sendTestPush,
} from './api'

/**
 * Уведомления на экран телефона (Web Push). Обработчик на стороне service
 * worker — public/push-sw.js, рассылка — backend notify_user.
 */

export type PushStatus =
  /** На сервере нет ключа VAPID — карточку не показываем вовсе. */
  | 'server-off'
  /** Браузер не умеет (старый, встроенный в мессенджер, iPhone не с главного экрана). */
  | 'unsupported'
  /** Человек запретил уведомления — включить снова можно только в настройках браузера. */
  | 'denied'
  | 'off'
  | 'on'

/** Кто включил уведомления в этом браузере: другой сотрудник, вошедший следом, их не наследует. */
const OWNER_KEY = 'waysklad:push-user'

let keyPromise: Promise<string | null> | null = null

function serverKey(): Promise<string | null> {
  keyPromise ??= getPushKey()
    .then((r) => r.public_key)
    .catch(() => {
      keyPromise = null // сеть моргнула — спросим снова при следующем открытии
      return null
    })
  return keyPromise
}

export function pushSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  )
}

/** SW регистрирует vite-plugin-pwa; в dev-режиме его нет — ждём недолго и сдаёмся. */
async function registration(): Promise<ServiceWorkerRegistration | null> {
  if (!('serviceWorker' in navigator)) return null
  const existing = await navigator.serviceWorker.getRegistration()
  if (existing) return existing
  return Promise.race([
    navigator.serviceWorker.ready,
    new Promise<null>((resolve) => setTimeout(() => resolve(null), 4000)),
  ])
}

function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer> {
  const base64 = (value + '='.repeat((4 - (value.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const bytes = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  return bytes
}

/** Подписка сделана с прежним ключом сервера — по ней ничего не дойдёт. */
function sameKey(subscription: PushSubscription, key: string): boolean {
  const current = subscription.options.applicationServerKey
  if (!current) return false
  const a = new Uint8Array(current)
  const b = base64UrlToBytes(key)
  return a.length === b.length && a.every((byte, i) => byte === b[i])
}

function rememberOwner(userId: number | null) {
  try {
    if (userId === null) localStorage.removeItem(OWNER_KEY)
    else localStorage.setItem(OWNER_KEY, String(userId))
  } catch {
    /* без localStorage не узнаем, кто включал, — sync тогда подписку не трогает */
  }
}

function rememberedOwner(): number | null {
  try {
    const value = localStorage.getItem(OWNER_KEY)
    return value ? Number(value) : null
  } catch {
    return null
  }
}

export async function readPushStatus(): Promise<PushStatus> {
  const key = await serverKey()
  if (!key) return 'server-off'
  if (!pushSupported()) return 'unsupported'
  if (Notification.permission === 'denied') return 'denied'
  const reg = await registration()
  if (!reg) return 'unsupported'
  const subscription = await reg.pushManager.getSubscription()
  return subscription && Notification.permission === 'granted' && sameKey(subscription, key) ? 'on' : 'off'
}

export interface EnableResult {
  status: PushStatus
  /** Пробное уведомление принято push-сервисом; false — сеть или сервис не ответили. */
  delivered?: boolean
}

/** Вызывать прямо из нажатия: Safari спрашивает разрешение только в ответ на жест. */
export async function enablePush(userId: number): Promise<EnableResult> {
  if (!pushSupported()) return { status: 'unsupported' }
  // Сначала окно разрешения, потом всё остальное: любое ожидание сети до него
  // Safari считает уже не жестом и молча отказывает.
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return { status: permission === 'denied' ? 'denied' : 'off' }

  const key = await serverKey()
  if (!key) return { status: 'server-off' }
  const reg = await registration()
  if (!reg) return { status: 'unsupported' }

  let subscription = await reg.pushManager.getSubscription()
  if (subscription && !sameKey(subscription, key)) {
    await subscription.unsubscribe()
    subscription = null
  }
  subscription ??= await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: base64UrlToBytes(key),
  })
  await savePushSubscription(subscription.toJSON())
  rememberOwner(userId)

  const { delivered } = await sendTestPush(subscription.endpoint)
  return { status: 'on', delivered }
}

/** Снять подписку этого браузера. token — при выходе, когда сессия уже стирается. */
export async function disablePush(token?: string): Promise<void> {
  rememberOwner(null)
  if (!pushSupported()) return
  const reg = await registration()
  const subscription = await reg?.pushManager.getSubscription()
  if (!subscription) return
  const { endpoint } = subscription
  await subscription.unsubscribe().catch(() => false)
  // сервер и сам забудет подписку по ответу 410, но лучше сразу
  await deletePushSubscription(endpoint, token).catch(() => undefined)
}

/**
 * При каждом открытии кабинета: подтвердить серверу подписку этого браузера.
 * Так она переживает смену пароля (новая версия сессии) и смену адреса
 * подписки браузером. Если включал другой сотрудник — снимаем, а не перехватываем.
 */
export async function syncPushSubscription(userId: number): Promise<void> {
  if (!pushSupported() || Notification.permission !== 'granted') return
  const key = await serverKey()
  if (!key) return
  const reg = await registration()
  const subscription = await reg?.pushManager.getSubscription()
  if (!subscription) return
  const owner = rememberedOwner()
  // не знаем, кто включал (хранилище недоступно или очищено), — не трогаем
  if (owner === null) return
  if (owner !== userId || !sameKey(subscription, key)) {
    await subscription.unsubscribe().catch(() => false)
    return
  }
  await savePushSubscription(subscription.toJSON()).catch(() => undefined)
}
