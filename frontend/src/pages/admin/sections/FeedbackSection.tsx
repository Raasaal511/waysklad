import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  getAdminFeedback,
  resolveAdminFeedback,
  type AdminFeedbackItem,
  type AdminFeedbackStatus,
  type AdminFeedbackTopic,
} from '../../../entities/admin/feedbackApi'
import { Lightbox } from '../../../shared/ui/Lightbox'
import layoutStyles from '../../../shared/ui/Layout.module.css'
import { handleAdminError } from '../shared'
import adminStyles from '../AdminPage.module.css'
import styles from './FeedbackSection.module.css'

interface SectionProps {
  logout: () => void
  refreshKey: number
  onLoaded: () => void
}

const TOPIC_LABELS: Record<AdminFeedbackTopic, string> = {
  question: 'Вопрос',
  bug: 'Ошибка',
  suggestion: 'Рекомендация',
}

const TOPIC_FILTERS: { id: AdminFeedbackTopic | null; label: string }[] = [
  { id: null, label: 'Все темы' },
  { id: 'bug', label: 'Ошибки' },
  { id: 'question', label: 'Вопросы' },
  { id: 'suggestion', label: 'Рекомендации' },
]

const ROLE_LABELS: Record<string, string> = {
  owner: 'владелец',
  manager: 'управляющий',
  seller: 'продавец',
  storekeeper: 'кладовщик',
  analyst: 'аналитик',
}

const EMPTY_TEXT: Record<AdminFeedbackStatus, string> = {
  new: 'Новых обращений нет — всё разобрано',
  resolved: 'Разобранных обращений пока нет',
  all: 'Обращений пока нет',
}

export function FeedbackSection({ logout, refreshKey, onLoaded }: SectionProps) {
  const [status, setStatus] = useState<AdminFeedbackStatus>('new')
  const [topic, setTopic] = useState<AdminFeedbackTopic | null>(null)
  const [items, setItems] = useState<AdminFeedbackItem[]>([])
  const [newCount, setNewCount] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [lightbox, setLightbox] = useState<{ photos: string[]; index: number } | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await getAdminFeedback({ status, topic: topic ?? undefined })
      setItems(data.items)
      setNewCount(data.new_count)
      setError(null)
    } catch (err) {
      setError(handleAdminError(err, logout))
    } finally {
      setLoading(false)
      onLoaded()
    }
  }, [status, topic, logout, onLoaded])

  useEffect(() => {
    load()
  }, [load, refreshKey])

  async function toggleResolved(item: AdminFeedbackItem) {
    setBusyId(item.id)
    try {
      await resolveAdminFeedback(item.id, item.resolved_at === null)
      await load()
    } catch (err) {
      setError(handleAdminError(err, logout))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className={styles.layout}>
      <div className={styles.toolbar}>
        <div className={adminStyles.filterTabs}>
          <FilterTab active={status === 'new'} onClick={() => setStatus('new')}>
            Новые · {newCount}
          </FilterTab>
          <FilterTab active={status === 'resolved'} onClick={() => setStatus('resolved')}>
            Разобранные
          </FilterTab>
          <FilterTab active={status === 'all'} onClick={() => setStatus('all')}>
            Все
          </FilterTab>
        </div>
        <div className={adminStyles.filterTabs}>
          {TOPIC_FILTERS.map((t) => (
            <FilterTab key={t.label} active={topic === t.id} onClick={() => setTopic(t.id)}>
              {t.label}
            </FilterTab>
          ))}
        </div>
      </div>

      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : error ? (
        <p className={layoutStyles.error}>{error}</p>
      ) : items.length === 0 ? (
        <p className={styles.empty}>{topic ? 'По этой теме ничего нет' : EMPTY_TEXT[status]}</p>
      ) : (
        <ul className={styles.list}>
          {items.map((item) => (
            <li key={item.id} className={styles.item} data-resolved={item.resolved_at !== null}>
              <div className={styles.head}>
                <span className={styles.topic} data-topic={item.topic}>
                  {TOPIC_LABELS[item.topic]}
                </span>
                <time className={styles.time} dateTime={item.created_at}>
                  {formatTime(item.created_at)}
                </time>
              </div>

              <div className={styles.author}>
                <Link to={`/admin/tenants/${item.tenant_id}`} className={styles.shop}>
                  {item.shop_name}
                </Link>
                <span className={styles.muted}>
                  {item.author_name} · {ROLE_LABELS[item.author_role] ?? item.author_role} ·{' '}
                  <a href={`tel:${item.author_phone}`}>{item.author_phone}</a>
                </span>
              </div>

              {item.text && <p className={styles.text}>{item.text}</p>}

              {item.photos.length > 0 && (
                <div className={styles.photos}>
                  {item.photos.map((url, index) => (
                    <button
                      key={url}
                      type="button"
                      className={styles.photo}
                      onClick={() => setLightbox({ photos: item.photos, index })}
                      aria-label={`Открыть фото ${index + 1}`}
                    >
                      <img src={url} alt="" loading="lazy" />
                    </button>
                  ))}
                </div>
              )}

              <div className={styles.foot}>
                <span className={styles.meta} title={item.user_agent}>
                  {[item.page && `Экран: ${item.page}`, shortDevice(item.user_agent), item.app_version]
                    .filter(Boolean)
                    .join(' · ')}
                </span>
                <button
                  type="button"
                  className={styles.resolve}
                  data-resolved={item.resolved_at !== null}
                  onClick={() => toggleResolved(item)}
                  disabled={busyId === item.id}
                >
                  {item.resolved_at === null ? 'Разобрано' : 'Вернуть в новые'}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {lightbox && (
        <Lightbox
          photos={lightbox.photos}
          index={lightbox.index}
          onClose={() => setLightbox(null)}
          onIndexChange={(index) => setLightbox((prev) => (prev ? { ...prev, index } : prev))}
        />
      )}
    </div>
  )
}

function formatTime(value: string): string {
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** «Android · Chrome» вместо полной строки браузера; полная — во всплывающей подсказке. */
function shortDevice(ua: string): string {
  if (!ua) return ''
  const os = /iPhone|iPad/.test(ua)
    ? 'iPhone'
    : /Android/.test(ua)
      ? 'Android'
      : /Windows/.test(ua)
        ? 'Windows'
        : /Mac OS X/.test(ua)
          ? 'Mac'
          : ''
  const browser = /YaBrowser/.test(ua)
    ? 'Яндекс Браузер'
    : /Edg\//.test(ua)
      ? 'Edge'
      : /Firefox|FxiOS/.test(ua)
        ? 'Firefox'
        : /CriOS|Chrome\//.test(ua)
          ? 'Chrome'
          : /Safari\//.test(ua)
            ? 'Safari'
            : ''
  return [os, browser].filter(Boolean).join(' · ') || ua.slice(0, 60)
}

function FilterTab({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button type="button" className={adminStyles.filterTab} data-active={active} onClick={onClick}>
      {children}
    </button>
  )
}
