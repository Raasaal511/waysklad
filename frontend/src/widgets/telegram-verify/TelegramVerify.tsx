import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  IconBrandTelegram,
  IconCircleCheckFilled,
  IconCopy,
  IconCheck,
  IconLoader2,
} from '@tabler/icons-react'
import {
  getTelegramVerification,
  resendTelegramCode,
  type TelegramStart,
  type TelegramVerificationStatus,
} from '../../entities/auth/api'
import { ApiError } from '../../shared/api/client'
import { Button } from '../../shared/ui/Button'
import styles from './TelegramVerify.module.css'

const POLL_MS = 2500
const RESEND_COOLDOWN_S = 60

interface TelegramVerifyProps {
  start: TelegramStart
  /** Код из бота; бросает ApiError — текст показывается под полем. */
  onConfirm: (code: string) => Promise<void>
  /** Ссылка устарела или человек хочет поправить данные. */
  onRestart: () => void
  restartLabel: string
  /** Ради чего подтверждаем — одна фраза под заголовком. */
  lead: string
}

function secondsSince(iso: string | null): number {
  if (!iso) return Infinity
  return (Date.now() - new Date(iso).getTime()) / 1000
}

/**
 * Подтверждение номера через бота: «Открыть Telegram» → «Поделиться номером»
 * в боте → код на сайте. Сайт сам узнаёт, что номер в боте подтверждён
 * (опрос статуса), и ставит курсор в поле кода — человек возвращается из
 * Telegram и сразу вводит цифры.
 */
export function TelegramVerify({ start, onConfirm, onRestart, restartLabel, lead }: TelegramVerifyProps) {
  const [status, setStatus] = useState<TelegramVerificationStatus | null>(null)
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [resendLeft, setResendLeft] = useState(0)
  const [resendNote, setResendNote] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const codeRef = useRef<HTMLInputElement>(null)
  const submittedCode = useRef<string | null>(null)

  const contactConfirmed = status?.contact_confirmed === true
  const expired = status?.expired === true

  // Опрос статуса: пока человек в Telegram. После возврата во вкладку —
  // сразу, не дожидаясь таймера.
  useEffect(() => {
    let alive = true
    let timer: number | undefined
    async function poll() {
      try {
        const next = await getTelegramVerification(start.token)
        if (!alive) return
        setStatus(next)
        if (next.expired || next.completed) return
      } catch {
        /* сеть моргнула — следующий опрос */
      }
      if (alive) timer = window.setTimeout(poll, POLL_MS)
    }
    void poll()
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        window.clearTimeout(timer)
        void poll()
      }
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      alive = false
      window.clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [start.token])

  useEffect(() => {
    if (contactConfirmed) codeRef.current?.focus()
  }, [contactConfirmed])

  // обратный отсчёт до «Отправить код ещё раз»
  useEffect(() => {
    if (!status?.code_sent_at) return
    const tick = () => setResendLeft(Math.max(0, Math.ceil(RESEND_COOLDOWN_S - secondsSince(status.code_sent_at))))
    tick()
    const timer = window.setInterval(tick, 1000)
    return () => window.clearInterval(timer)
  }, [status?.code_sent_at])

  async function submit(value: string) {
    if (value.length !== 6 || submitting) return
    submittedCode.current = value
    setSubmitting(true)
    setError(null)
    try {
      await onConfirm(value)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось проверить код')
      setCode('')
      codeRef.current?.focus()
    } finally {
      setSubmitting(false)
    }
  }

  function handleCodeChange(raw: string) {
    const digits = raw.replace(/\D/g, '').slice(0, 6)
    setCode(digits)
    setError(null)
    // шесть цифр — сразу проверяем: одно действие меньше (и вставка из буфера тоже)
    if (digits.length === 6 && submittedCode.current !== digits) void submit(digits)
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    void submit(code)
  }

  async function handleResend() {
    setResendNote(null)
    setError(null)
    try {
      await resendTelegramCode(start.token)
      setStatus((s) => (s ? { ...s, code_sent_at: new Date().toISOString() } : s))
      setResendNote('Новый код отправлен в Telegram')
      submittedCode.current = null
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось отправить код')
    }
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(start.telegram_link)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      /* без буфера ссылка всё равно открывается кнопкой */
    }
  }

  if (expired) {
    return (
      <div className={styles.wrap}>
        <div className={styles.head}>
          <span className={styles.logo} aria-hidden="true">
            <IconBrandTelegram size={28} stroke={1.6} />
          </span>
          <h2 className={styles.title}>Ссылка устарела</h2>
          <p className={styles.lead}>Она действует 30 минут. Получите новую — данные формы сохранятся.</p>
        </div>
        <Button className={styles.primary} onClick={onRestart}>
          {restartLabel}
        </Button>
      </div>
    )
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <span className={styles.logo} aria-hidden="true">
          <IconBrandTelegram size={28} stroke={1.6} />
        </span>
        <h2 className={styles.title}>Подтвердите номер в Telegram</h2>
        <p className={styles.lead}>{lead}</p>
      </div>

      <ol className={styles.steps}>
        <li className={styles.step} data-done={contactConfirmed || undefined}>
          <span className={styles.stepMark} aria-hidden="true">
            {contactConfirmed ? <IconCircleCheckFilled size={24} /> : 1}
          </span>
          <div className={styles.stepBody}>
            <strong>Откройте бота ВайСклад</strong>
            {!contactConfirmed && (
              <>
                <a className={styles.telegramButton} href={start.telegram_link} target="_blank" rel="noreferrer">
                  <IconBrandTelegram size={20} stroke={1.8} /> Открыть Telegram
                </a>
                <button type="button" className={styles.copyLink} onClick={handleCopy}>
                  {copied ? <IconCheck size={16} stroke={2} /> : <IconCopy size={16} stroke={1.8} />}
                  {copied ? 'Ссылка скопирована' : 'Telegram на другом устройстве? Скопировать ссылку'}
                </button>
              </>
            )}
          </div>
        </li>
        <li className={styles.step} data-done={contactConfirmed || undefined}>
          <span className={styles.stepMark} aria-hidden="true">
            {contactConfirmed ? <IconCircleCheckFilled size={24} /> : 2}
          </span>
          <div className={styles.stepBody}>
            <strong>Нажмите в боте {'«📱\u00a0Поделиться\u00a0номером»'}</strong>
            <span className={styles.stepHint} role="status">
              {contactConfirmed ? (
                'Номер подтверждён — код уже в Telegram'
              ) : (
                <>
                  <IconLoader2 size={16} stroke={2} className={styles.spinner} aria-hidden="true" />
                  Ждём ваш номер из Telegram…
                </>
              )}
            </span>
          </div>
        </li>
        <li className={styles.step} data-active={contactConfirmed || undefined}>
          <span className={styles.stepMark} aria-hidden="true">
            3
          </span>
          <form className={styles.stepBody} onSubmit={handleSubmit}>
            <label htmlFor="telegram-code">
              <strong>Введите код из сообщения бота</strong>
            </label>
            <input
              id="telegram-code"
              ref={codeRef}
              className={styles.code}
              value={code}
              onChange={(e) => handleCodeChange(e.target.value)}
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="\d{6}"
              maxLength={6}
              placeholder="••••••"
              disabled={!contactConfirmed || submitting}
              aria-invalid={error ? true : undefined}
            />
            {error && (
              <p className={styles.error} role="alert">
                {error}
              </p>
            )}
            {resendNote && !error && <p className={styles.note}>{resendNote}</p>}
            <Button type="submit" className={styles.primary} disabled={!contactConfirmed || code.length !== 6 || submitting}>
              {submitting ? 'Проверяем…' : 'Подтвердить'}
            </Button>
            {contactConfirmed && (
              <button type="button" className={styles.link} onClick={handleResend} disabled={resendLeft > 0}>
                {resendLeft > 0 ? `Отправить код ещё раз через ${resendLeft}\u00a0с` : 'Отправить код ещё раз'}
              </button>
            )}
          </form>
        </li>
      </ol>

      <button type="button" className={styles.link} onClick={onRestart}>
        {restartLabel}
      </button>
    </div>
  )
}
