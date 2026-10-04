import { useCallback, useEffect, useState, type ReactNode } from 'react'
import {
  IconCircleCheck,
  IconCopy,
  IconDeviceMobile,
  IconDots,
  IconDotsVertical,
  IconShare2,
  IconSquarePlus,
  IconCheck,
} from '@tabler/icons-react'
import { copyText } from '../../shared/lib/clipboard'
import { usePwaInstall, type PwaInstallState } from '../../shared/lib/pwaInstall'
import { Button } from '../../shared/ui/Button'
import { Modal } from '../../shared/ui/Modal'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './AppInstallCard.module.css'

/**
 * «Приложение на телефоне»: одна кнопка «Установить приложение» для всех.
 * Где браузер умеет ставить сам (Chrome на Android и компьютере) — системное окно,
 * где нет (iPhone, встроенный браузер мессенджера) — шторка с подсказкой.
 */
export function AppInstallCard() {
  const pwa = usePwaInstall()
  const [sheetOpen, setSheetOpen] = useState(false)
  const closeSheet = useCallback(() => setSheetOpen(false), [])

  async function handleInstall() {
    if (pwa.canPrompt && (await pwa.install()) !== 'unavailable') return
    setSheetOpen(true)
  }

  return (
    <div className={[layoutStyles.card, layoutStyles.cardFull, styles.card].join(' ')}>
      <div className={styles.head}>
        <span className={styles.icon} aria-hidden>
          <IconDeviceMobile size={24} stroke={1.7} />
        </span>
        <div className={styles.headText}>
          <h3>Приложение на телефоне</h3>
          {pwa.accepted ? (
            <span className={styles.done}>
              Готово, иконка на главном экране
              <IconCircleCheck size={20} stroke={2} className={styles.doneIcon} aria-hidden />
            </span>
          ) : pwa.installed ? (
            <>
              <span className={styles.done}>
                Приложение установлено
                <IconCircleCheck size={20} stroke={2} className={styles.doneIcon} aria-hidden />
              </span>
              <span className={layoutStyles.textMuted}>
                {pwa.os === 'desktop'
                  ? 'Открывайте его с иконки «WaySklad», как обычную программу.'
                  : 'Открывайте его с иконки «WaySklad» на главном экране.'}
              </span>
            </>
          ) : (
            <span className={layoutStyles.textMuted}>
              Открывается с иконки на экране — не нужно искать ссылку.
            </span>
          )}
        </div>
      </div>

      {!pwa.accepted && !pwa.installed && (
        <Button className={styles.action} onClick={handleInstall}>
          Установить приложение
        </Button>
      )}

      {sheetOpen && <InstallSheet pwa={pwa} onClose={closeSheet} />}
    </div>
  )
}

const SHEET_TITLES: Record<PwaInstallState['platform'], string> = {
  'ios-share': 'Как установить',
  'ios-need-safari': 'Откройте в Safari',
  'in-app': 'Откройте в браузере',
  browser: 'Установка через меню',
}

export function InstallSheet({ pwa, onClose }: { pwa: PwaInstallState; onClose: () => void }) {
  const MenuIcon = pwa.os === 'ios' ? IconDots : IconDotsVertical
  const menuSign = pwa.os === 'ios' ? '•••' : '⋮'

  return (
    <Modal title={SHEET_TITLES[pwa.platform]} onClose={onClose}>
      {pwa.platform === 'ios-share' && (
        <ol className={styles.steps}>
          <Step icon={<IconShare2 size={24} stroke={1.8} />} title="Нажмите «Поделиться»">
            Значок со стрелкой — внизу или вверху экрана, иногда в меню •••
          </Step>
          <Step icon={<IconSquarePlus size={24} stroke={1.8} />} title="Выберите «На экран „Домой“»">
            Если не видно — пролистайте список вниз
          </Step>
          <Step icon={<IconCheck size={24} stroke={2} />} title="Нажмите «Добавить»">
            Справа вверху. Иконка появится на главном экране
          </Step>
        </ol>
      )}

      {pwa.platform === 'ios-need-safari' && (
        <div className={styles.sheetBody}>
          <p className={styles.lead}>
            На этом iPhone приложение ставится только из Safari. Скопируйте ссылку, откройте её в
            Safari и снова нажмите «Установить приложение».
          </p>
          <CopyLinkButton />
        </div>
      )}

      {pwa.platform === 'in-app' && (
        <div className={styles.sheetBody}>
          <p className={styles.lead}>
            Ссылка открыта внутри {pwa.inAppName ?? 'другого приложения'} — отсюда установить нельзя.
          </p>
          <ol className={styles.steps}>
            <Step icon={<MenuIcon size={24} stroke={2} />} title={`Нажмите ${menuSign} → «Открыть в браузере»`}>
              Там снова нажмите «Установить приложение»
            </Step>
          </ol>
          <CopyLinkButton />
        </div>
      )}

      {pwa.platform === 'browser' && (
        <ol className={styles.steps}>
          <Step
            icon={<MenuIcon size={24} stroke={2} />}
            title="В меню браузера выберите «Установить приложение» или «Добавить на главный экран»"
          >
            Меню — значок {menuSign} в углу экрана
          </Step>
        </ol>
      )}
    </Modal>
  )
}

function Step({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <li className={styles.step}>
      <span className={styles.icon} aria-hidden>
        {icon}
      </span>
      <span className={styles.stepText}>
        <strong>{title}</strong>
        <span className={layoutStyles.textMuted}>{children}</span>
      </span>
    </li>
  )
}

function CopyLinkButton() {
  const [status, setStatus] = useState<'idle' | 'copied' | 'failed'>('idle')

  useEffect(() => {
    if (status === 'idle') return
    const timer = setTimeout(() => setStatus('idle'), 2500)
    return () => clearTimeout(timer)
  }, [status])

  async function handleCopy() {
    setStatus((await copyText(window.location.href)) ? 'copied' : 'failed')
  }

  return (
    <Button className={styles.action} onClick={handleCopy}>
      {status === 'copied' ? <IconCheck size={20} stroke={2} /> : <IconCopy size={20} stroke={1.8} />}
      {status === 'copied'
        ? 'Ссылка скопирована'
        : status === 'failed'
          ? 'Не вышло — скопируйте из адресной строки'
          : 'Скопировать ссылку'}
    </Button>
  )
}
