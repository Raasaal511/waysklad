import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { IconBug, IconBulb, IconCircleCheck, IconHelpCircle, IconPhotoPlus, IconX } from '@tabler/icons-react'
import {
  FEEDBACK_MAX_PHOTO_BYTES,
  FEEDBACK_MAX_PHOTOS,
  FEEDBACK_MAX_TEXT,
  sendFeedback,
  type FeedbackTopic,
} from '../../entities/feedback/api'
import { ApiError } from '../../shared/api/client'
import { Button } from '../../shared/ui/Button'
import { Modal } from '../../shared/ui/Modal'
import styles from './FeedbackModal.module.css'

const TOPICS: {
  id: FeedbackTopic
  label: string
  icon: typeof IconBug
  placeholder: string
}[] = [
  {
    id: 'question',
    label: 'Вопрос',
    icon: IconHelpCircle,
    placeholder: 'Что хотите узнать?',
  },
  {
    id: 'bug',
    label: 'Ошибка',
    icon: IconBug,
    placeholder: 'Что случилось и что вы делали перед этим?',
  },
  {
    id: 'suggestion',
    label: 'Рекомендация',
    icon: IconBulb,
    placeholder: 'Что добавить или сделать удобнее?',
  },
]

interface PickedPhoto {
  file: File
  preview: string
}

/**
 * Обратная связь из кабинета: тема → текст и/или фото → «Отправить».
 * Магазин, автор, экран и устройство сервер узнаёт сам — человек их не пишет.
 */
export function FeedbackModal({ onClose }: { onClose: () => void }) {
  const [topic, setTopic] = useState<FeedbackTopic | null>(null)
  const [text, setText] = useState('')
  const [photos, setPhotos] = useState<PickedPhoto[]>([])
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // превью живут в памяти браузера, пока их не освободить — помним выданные адреса
  const previewUrls = useRef(new Set<string>())
  useEffect(() => {
    const urls = previewUrls.current
    return () => urls.forEach((url) => URL.revokeObjectURL(url))
  }, [])

  const missing = !topic
    ? 'Выберите тему'
    : !text.trim() && photos.length === 0
      ? 'Напишите пару слов или прикрепите фото'
      : null

  function handleFiles(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    e.target.value = '' // то же фото можно выбрать снова после удаления
    const room = FEEDBACK_MAX_PHOTOS - photos.length
    const tooBig = files.some((f) => f.size > FEEDBACK_MAX_PHOTO_BYTES)
    const accepted = files.filter((f) => f.size <= FEEDBACK_MAX_PHOTO_BYTES).slice(0, room)
    setError(
      tooBig
        ? 'Фото больше 5 МБ не прикрепить — сделайте скриншот поменьше'
        : files.length > room
          ? `Можно прикрепить не больше ${FEEDBACK_MAX_PHOTOS} фото`
          : null,
    )
    const picked = accepted.map((file) => ({
      file,
      preview: URL.createObjectURL(file),
    }))
    picked.forEach((p) => previewUrls.current.add(p.preview))
    setPhotos((prev) => [...prev, ...picked])
  }

  function removePhoto(preview: string) {
    URL.revokeObjectURL(preview)
    previewUrls.current.delete(preview)
    setPhotos((prev) => prev.filter((p) => p.preview !== preview))
  }

  async function handleSubmit() {
    if (!topic || missing || sending) return
    setSending(true)
    setError(null)
    try {
      await sendFeedback({
        topic,
        text: text.trim(),
        photos: photos.map((p) => p.file),
      })
      setSent(true)
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Нет связи с сервером — проверьте интернет и попробуйте ещё раз',
      )
    } finally {
      setSending(false)
    }
  }

  const placeholder =
    TOPICS.find((t) => t.id === topic)?.placeholder ?? 'Опишите, что случилось или что хотите предложить'

  return (
    <Modal
      title="Обратная связь"
      onClose={onClose}
      footer={
        sent ? undefined : (
          <div className={styles.footer}>
            <Button className={styles.submit} onClick={handleSubmit} disabled={!!missing || sending}>
              {sending ? 'Отправляем…' : 'Отправить'}
            </Button>
            {missing && <span className={styles.hint}>{missing}</span>}
          </div>
        )
      }
    >
      {sent ? (
        <div className={styles.thanks}>
          <IconCircleCheck size={48} stroke={1.6} className={styles.thanksIcon} aria-hidden />
          <strong>Спасибо, получили</strong>
          <span className={styles.muted}>Посмотрим в ближайшее время.</span>
          <Button className={styles.submit} onClick={onClose}>
            Готово
          </Button>
        </div>
      ) : (
        <div className={styles.form}>
          <div className={styles.topics} role="radiogroup" aria-label="Тема">
            {TOPICS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="radio"
                aria-checked={topic === t.id}
                className={[styles.topic, topic === t.id && styles.topicActive].filter(Boolean).join(' ')}
                onClick={() => setTopic(t.id)}
              >
                <t.icon size={22} stroke={1.8} aria-hidden />
                <span>{t.label}</span>
              </button>
            ))}
          </div>

          <label className={styles.field}>
            <span className={styles.label}>Описание</span>
            <textarea
              className={styles.textarea}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={placeholder}
              maxLength={FEEDBACK_MAX_TEXT}
              rows={4}
            />
            {text.length > FEEDBACK_MAX_TEXT - 200 && (
              <span className={styles.counter}>
                {text.length} / {FEEDBACK_MAX_TEXT}
              </span>
            )}
          </label>

          <div className={styles.field}>
            <span className={styles.label}>Фото или скриншот</span>
            <div className={styles.photos}>
              {photos.map((p) => (
                <div key={p.preview} className={styles.photo}>
                  <img src={p.preview} alt="" />
                  <button
                    type="button"
                    className={styles.photoRemove}
                    onClick={() => removePhoto(p.preview)}
                    aria-label="Убрать фото"
                  >
                    <IconX size={14} stroke={2.2} />
                  </button>
                </div>
              ))}
              {photos.length < FEEDBACK_MAX_PHOTOS && (
                <button
                  type="button"
                  className={styles.photoAdd}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <IconPhotoPlus size={22} stroke={1.7} aria-hidden />
                  <span>Фото</span>
                </button>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                hidden
                onChange={handleFiles}
              />
            </div>
          </div>

          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
        </div>
      )}
    </Modal>
  )
}
