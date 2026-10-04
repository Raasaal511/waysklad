import { useEffect, useRef, useState } from 'react'
import { IconAlertTriangle, IconCheck, IconCircleCheck, IconCopy, IconRefresh, IconShare2 } from '@tabler/icons-react'
import { copyText } from '../../shared/lib/clipboard'
import { generatePassword } from '../../shared/lib/password'
import { Button } from '../../shared/ui/Button'
import { Modal } from '../../shared/ui/Modal'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './EmployeeCredentials.module.css'

export interface Credentials {
  name: string
  roleLabel: string
  phone: string
  password: string
}

function credentialsText(c: Credentials): string {
  return [
    `Доступ к ВайСклад для ${c.name} (${c.roleLabel.toLowerCase()})`,
    `Вход: ${window.location.origin}/login`,
    `Телефон: ${c.phone}`,
    `Пароль: ${c.password}`,
  ].join('\n')
}

/** Поле пароля сотрудника: сразу заполнено случайным паролем и видно — его
 *  всё равно нужно передать человеку, прятать за точками незачем. */
export function PasswordField({
  value,
  onChange,
  label = 'Пароль',
}: {
  value: string
  onChange: (value: string) => void
  label?: string
}) {
  return (
    <label className={layoutStyles.field}>
      {label}
      <div className={styles.passwordRow}>
        <input
          className={styles.passwordInput}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required
          minLength={6}
          autoComplete="new-password"
          spellCheck={false}
        />
        <Button type="button" variant="secondary" className={styles.generate} onClick={() => onChange(generatePassword())}>
          <IconRefresh size={18} stroke={1.8} /> Придумать
        </Button>
      </div>
    </label>
  )
}

/**
 * Итог создания сотрудника (или смены пароля): данные уже в буфере — их
 * остаётся вставить в мессенджер. Пароль показывается только здесь.
 */
export function CredentialsModal({
  credentials,
  title,
  onClose,
}: {
  credentials: Credentials
  title: string
  onClose: () => void
}) {
  const text = credentialsText(credentials)
  const [copied, setCopied] = useState<boolean | null>(null)
  const copiedOnce = useRef(false)
  const canShare = typeof navigator !== 'undefined' && typeof navigator.share === 'function'

  // Сразу в буфер: на телефоне владелец следующим действием открывает мессенджер.
  useEffect(() => {
    if (copiedOnce.current) return
    copiedOnce.current = true
    void copyText(text).then(setCopied)
  }, [text])

  async function copyAgain() {
    setCopied(await copyText(text))
  }

  async function share() {
    try {
      await navigator.share({ title: 'Доступ к ВайСклад', text })
    } catch {
      /* закрыли окно «Поделиться» — ничего страшного */
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <div className={styles.wrap}>
        <p className={copied === false ? styles.copyFailed : styles.copied} role="status">
          {copied === false ? (
            'Скопировать автоматически не получилось — нажмите «Скопировать».'
          ) : (
            <>
              <IconCircleCheck size={20} stroke={2} aria-hidden="true" />
              Данные для входа скопированы — отправьте их сотруднику
            </>
          )}
        </p>

        <dl className={styles.card}>
          <div>
            <dt>Сотрудник</dt>
            <dd>
              {credentials.name} · {credentials.roleLabel}
            </dd>
          </div>
          <div>
            <dt>Вход</dt>
            <dd>{window.location.host}/login</dd>
          </div>
          <div>
            <dt>Телефон</dt>
            <dd>{credentials.phone}</dd>
          </div>
          <div>
            <dt>Пароль</dt>
            <dd className={styles.password}>{credentials.password}</dd>
          </div>
        </dl>

        <p className={styles.warning}>
          <IconAlertTriangle size={20} stroke={1.8} aria-hidden="true" />
          <span>
            Запишите телефон и пароль или отправьте их сейчас — после закрытия окна пароль больше не
            будет видно. Если сотрудник забудет, задайте новый в его карточке.
          </span>
        </p>

        <div className={styles.actions}>
          {canShare && (
            <Button onClick={share}>
              <IconShare2 size={18} stroke={1.8} /> Отправить
            </Button>
          )}
          <Button variant="secondary" onClick={copyAgain}>
            {copied ? <IconCheck size={18} stroke={2} /> : <IconCopy size={18} stroke={1.8} />}
            Скопировать
          </Button>
          <Button variant="secondary" onClick={onClose}>
            Готово
          </Button>
        </div>
      </div>
    </Modal>
  )
}
