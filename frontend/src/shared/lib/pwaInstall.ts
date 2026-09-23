import { useSyncExternalStore } from 'react'

/**
 * Установка приложения на главный экран (кнопка в профиле).
 *
 * `beforeinstallprompt` Chrome присылает один раз за загрузку и часто раньше,
 * чем человек дойдёт до профиля, — поэтому слушаем с самого старта
 * (`initPwaInstall()` в main.tsx), а профиль только читает состояние.
 */

/** Событие Chrome; в lib.dom его нет. */
interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>
  readonly userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

/** Что умеет браузер, в котором открыта страница. */
export type InstallPlatform =
  /** iPhone/iPad: Safari или браузер на iOS 16.4+ — «Поделиться → На экран „Домой“». */
  | 'ios-share'
  /** iPhone не в Safari на iOS ниже 16.4 — ставится только из Safari. */
  | 'ios-need-safari'
  /** Встроенный браузер мессенджера — установки нет вовсе, нужен обычный браузер. */
  | 'in-app'
  /** Android и компьютер: системное окно по событию или пункт в меню браузера. */
  | 'browser'

export interface PwaInstallState {
  /** Открыто с иконки, Chrome подтвердил установку или она прошла в этой сессии. */
  installed: boolean
  /** Браузер дал событие — `install()` откроет системное окно «Установить?». */
  canPrompt: boolean
  /** Человек согласился в системном окне в этой сессии. */
  accepted: boolean
  platform: InstallPlatform
  os: 'ios' | 'android' | 'desktop'
  /** Чей встроенный браузер, если узнали: WhatsApp, Telegram, Instagram. */
  inAppName: string | null
}

type NavigatorWithApps = Navigator & {
  standalone?: boolean
  getInstalledRelatedApps?: () => Promise<unknown[]>
}

let deferred: BeforeInstallPromptEvent | null = null
let accepted = false
/** Ответ Chrome на getInstalledRelatedApps (манифест ссылается сам на себя). */
let relatedInstalled = false
let installedThisSession = false
let started = false
const listeners = new Set<() => void>()
const platformInfo = detectPlatform(
  typeof navigator === 'undefined' ? '' : navigator.userAgent,
  typeof navigator === 'undefined' ? 0 : navigator.maxTouchPoints,
  typeof window !== 'undefined' && 'TelegramWebviewProxy' in window,
)
let snapshot = buildSnapshot()

/** Версия iOS как 1604 для 16.4; null, если по строке браузера не понять. */
function iosVersion(ua: string): number | null {
  const m = ua.match(/OS (\d+)_(\d+)/) ?? ua.match(/Version\/(\d+)\.(\d+)/)
  return m ? Number(m[1]) * 100 + Number(m[2]) : null
}

export function detectPlatform(
  ua: string,
  maxTouchPoints: number,
  telegramProxy: boolean,
): Pick<PwaInstallState, 'platform' | 'os' | 'inAppName'> {
  // iPad с iPadOS 13+ представляется Mac’ом — выдаёт его только сенсорный экран.
  const isIos = /iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && maxTouchPoints > 1)
  const os = isIos ? 'ios' : /Android/i.test(ua) ? 'android' : 'desktop'

  const inAppName = /WhatsApp/i.test(ua)
    ? 'WhatsApp'
    : /Telegram/i.test(ua) || telegramProxy
      ? 'Telegram'
      : /Instagram/i.test(ua)
        ? 'Instagram'
        : null
  // Остальные встроенные браузеры узнаём по признакам WebView: «; wv)» на Android,
  // отсутствие «Safari/» на iOS (его пишут и Safari, и Chrome, и Яндекс на iPhone).
  const webView = os === 'android' ? /; wv\)/.test(ua) : os === 'ios' && !/Safari\//.test(ua)
  if (inAppName || webView) return { platform: 'in-app', os, inAppName }

  if (os === 'ios') {
    const safari = !/CriOS|FxiOS|EdgiOS|OPiOS|YaBrowser|GSA\//.test(ua)
    const version = iosVersion(ua)
    const needSafari = !safari && version !== null && version < 1604
    return { platform: needSafari ? 'ios-need-safari' : 'ios-share', os, inAppName: null }
  }
  return { platform: 'browser', os, inAppName: null }
}

function isStandalone(): boolean {
  if (typeof window === 'undefined') return false
  const iosStandalone = (navigator as NavigatorWithApps).standalone === true
  return iosStandalone || window.matchMedia?.('(display-mode: standalone)').matches === true
}

/**
 * Обычной вкладке браузер сам не говорит, что приложение уже стоит, — спрашиваем.
 * Chrome (Android и компьютер) отвечает честно, в том числе после удаления;
 * остальные браузеры метода не знают — там «установлено» только с иконки.
 */
async function checkRelatedInstalled() {
  const nav = navigator as NavigatorWithApps
  if (!nav.getInstalledRelatedApps) return
  try {
    const found = (await nav.getInstalledRelatedApps()).length > 0
    if (found !== relatedInstalled) {
      relatedInstalled = found
      emit()
    }
  } catch {
    /* не верхнее окно или браузер отказал — остаёмся при своём */
  }
}

function buildSnapshot(): PwaInstallState {
  return {
    ...platformInfo,
    installed: isStandalone() || relatedInstalled || installedThisSession,
    canPrompt: deferred !== null,
    accepted,
  }
}

function emit() {
  snapshot = buildSnapshot()
  listeners.forEach((listener) => listener())
}

/** Подписаться на события установки. Вызывается один раз, до рендера (main.tsx). */
export function initPwaInstall() {
  if (started || typeof window === 'undefined') return
  started = true

  window.addEventListener('beforeinstallprompt', (e) => {
    // Без preventDefault Chrome сам покажет свою плашку — установка только из профиля.
    e.preventDefault()
    deferred = e as BeforeInstallPromptEvent
    // Событие приходит, только когда приложения нет, — значит, его удалили.
    relatedInstalled = false
    installedThisSession = false
    emit()
  })
  window.addEventListener('appinstalled', () => {
    deferred = null
    installedThisSession = true
    emit()
  })
  // Удалить могли в другом окне — переспрашиваем, когда вкладка снова на экране.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') void checkRelatedInstalled()
  })
  void checkRelatedInstalled()
  // Chrome на компьютере умеет перенести вкладку в окно приложения — display-mode меняется на лету.
  window.matchMedia?.('(display-mode: standalone)').addEventListener?.('change', emit)
  emit()
}

/** Открыть системное окно «Установить?». Без события браузера — 'unavailable'. */
export async function installPwa(): Promise<'accepted' | 'dismissed' | 'unavailable'> {
  const event = deferred
  if (!event) return 'unavailable'
  // prompt() у события срабатывает один раз; после отказа — только меню браузера.
  deferred = null
  try {
    await event.prompt()
    const { outcome } = await event.userChoice
    if (outcome === 'accepted') accepted = true
    return outcome
  } catch {
    return 'unavailable'
  } finally {
    emit()
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function usePwaInstall(): PwaInstallState & { install: typeof installPwa } {
  const state = useSyncExternalStore(subscribe, () => snapshot)
  return { ...state, install: installPwa }
}
