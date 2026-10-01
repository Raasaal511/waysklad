import { useCallback, useEffect, useState } from 'react'
import { IconBell, IconCircleCheck } from '@tabler/icons-react'
import { useAuth } from '../../app/AuthContext'
import {
  disablePush,
  enablePush,
  readPushStatus,
  type PushStatus,
} from '../../entities/notification/push'
import { usePwaInstall, type PwaInstallState } from '../../shared/lib/pwaInstall'
import { Button } from '../../shared/ui/Button'
import layoutStyles from '../../shared/ui/Layout.module.css'
import { InstallSheet } from './AppInstallCard'
import installStyles from './AppInstallCard.module.css'
import styles from './PushCard.module.css'

/**
 * «Уведомления на телефоне»: одна кнопка. Приходит всё то же, что в колокольчике
 * (заявка с витрины, товар заканчивается, долги, задачи), — без настроек по типам.
 */
export function PushCard() {
  const { user } = useAuth()
  const pwa = usePwaInstall()
  const [status, setStatus] = useState<PushStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState<{ text: string; danger?: boolean } | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)
  const closeSheet = useCallback(() => setSheetOpen(false), [])

  useEffect(() => {
    let alive = true
    void readPushStatus().then((s) => alive && setStatus(s))
    return () => {
      alive = false
    }
  }, [])

  // На сервере push не настроен — карточка не нужна. Пока не знаем — не мигаем.
  if (status === null || status === 'server-off' || !user) return null

  async function handleEnable() {
    if (!user) return
    setBusy(true)
    setNote(null)
    try {
      const result = await enablePush(user.id)
      setStatus(result.status)
      if (result.status === 'on') {
        setNote(
          result.delivered
            ? { text: 'Отправили пробное уведомление — оно появится через пару секунд.' }
            : {
                text: 'Пробное уведомление не дошло. Проверьте интернет и включите ещё раз.',
                danger: true,
              },
        )
      }
    } catch {
      setNote({ text: 'Не получилось включить. Попробуйте ещё раз.', danger: true })
    } finally {
      setBusy(false)
    }
  }

  async function handleDisable() {
    setBusy(true)
    setNote(null)
    try {
      await disablePush()
      setStatus('off')
    } finally {
      setBusy(false)
    }
  }

  // iPhone пускает уведомления только в приложение с главного экрана — в Safari
  // PushManager просто нет. Ведём к установке той же шторкой, что и карточка выше.
  const needsInstall = status === 'unsupported' && pwa.os === 'ios' && !pwa.installed
  const inApp = status === 'unsupported' && pwa.platform === 'in-app'

  return (
    <div className={[layoutStyles.card, layoutStyles.cardFull, installStyles.card].join(' ')}>
      <div className={installStyles.head}>
        <span className={installStyles.icon} aria-hidden>
          <IconBell size={24} stroke={1.7} />
        </span>
        <div className={installStyles.headText}>
          <h3>{pwa.os === 'desktop' ? 'Уведомления на компьютере' : 'Уведомления на телефоне'}</h3>
          {status === 'on' ? (
            <span className={installStyles.done}>
              Включены на этом{' '}
              {/* галочка переносится только вместе с последним словом */}
              <span className={styles.nowrap}>
                устройстве
                <IconCircleCheck size={20} stroke={2} className={installStyles.doneIcon} aria-hidden />
              </span>
            </span>
          ) : (
            <span className={layoutStyles.textMuted}>{describe(status, pwa, needsInstall, inApp)}</span>
          )}
          {note && (
            <span
              className={[note.danger ? layoutStyles.textDanger : layoutStyles.textMuted, styles.note].join(' ')}
              role="status"
            >
              {note.text}
            </span>
          )}
        </div>
      </div>

      {status === 'off' && (
        <Button className={installStyles.action} onClick={handleEnable} disabled={busy}>
          {busy ? 'Включаем…' : 'Включить уведомления'}
        </Button>
      )}
      {status === 'on' && (
        <Button variant="secondary" className={installStyles.action} onClick={handleDisable} disabled={busy}>
          Выключить
        </Button>
      )}
      {(needsInstall || inApp) && (
        <Button className={installStyles.action} onClick={() => setSheetOpen(true)}>
          {needsInstall ? 'Как установить' : 'Как открыть в браузере'}
        </Button>
      )}

      {sheetOpen && <InstallSheet pwa={pwa} onClose={closeSheet} />}
    </div>
  )
}

function describe(status: PushStatus, pwa: PwaInstallState, needsInstall: boolean, inApp: boolean): string {
  if (needsInstall) return 'На iPhone уведомления приходят только в установленное приложение — сначала добавьте его на экран «Домой».'
  if (inApp) return `Внутри ${pwa.inAppName ?? 'мессенджера'} уведомления не работают — откройте кабинет в обычном браузере.`
  if (status === 'unsupported') return 'Этот браузер не умеет присылать уведомления. Откройте кабинет в Chrome или Safari.'
  if (status === 'denied') {
    if (pwa.os === 'ios') return 'Уведомления запрещены. Разрешите: Настройки iPhone → Уведомления → WaySklad.'
    if (pwa.installed && pwa.os === 'android')
      return 'Уведомления запрещены. Разрешите: Настройки телефона → Приложения → WaySklad → Уведомления.'
    return 'Уведомления запрещены в браузере. Разрешите: значок слева от адреса сайта → Уведомления.'
  }
  return 'Новая заявка, товар на исходе, долги и задачи — сразу на экран, даже когда кабинет закрыт.'
}
