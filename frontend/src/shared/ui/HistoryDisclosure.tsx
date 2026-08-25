import { useState } from 'react'
import { IconChevronDown, IconPencil, type Icon as TablerIcon } from '@tabler/icons-react'
import layoutStyles from './Layout.module.css'
import styles from './HistoryDisclosure.module.css'

export interface HistoryEntryLike {
  id: number
  action: string
  created_at: string
  user_name?: string | null
  details?: Record<string, unknown>
}

interface HistoryDisclosureProps<T extends HistoryEntryLike> {
  load: () => Promise<T[]>
  actionLabels: Record<string, string>
  actionIcons?: Record<string, TablerIcon>
  renderIcon?: (entry: T) => TablerIcon
  /** Человекочитаемая расшифровка details конкретного действия (сумма, старое/новое
   * значение и т.п.) — у каждой сущности details устроены по-своему. */
  formatDetail?: (entry: T) => string | null
  defaultIcon?: TablerIcon
  emptyMessage?: string
  label?: string
}

/** Сворачиваемая история изменений сущности (продажа/заказ/товар/долг/задача) —
 * общий вид для истории действий, встроенный в карточку самой сущности вместо
 * отдельного глобального журнала. */
export function HistoryDisclosure<T extends HistoryEntryLike>({
  load,
  actionLabels,
  actionIcons,
  renderIcon,
  formatDetail,
  defaultIcon = IconPencil,
  emptyMessage = 'Изменений не было',
  label = 'История изменений',
}: HistoryDisclosureProps<T>) {
  const [entries, setEntries] = useState<T[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)

  async function toggle() {
    if (open) {
      setOpen(false)
      return
    }
    setOpen(true)
    if (entries !== null) return
    setLoading(true)
    try {
      setEntries(await load())
    } catch {
      setEntries([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.history}>
      <button
        type="button"
        className={layoutStyles.disclosureLink}
        onClick={toggle}
        disabled={loading}
        aria-expanded={open}
      >
        {loading ? 'Загрузка…' : label}
        <IconChevronDown size={14} stroke={1.8} />
      </button>
      {open &&
        (entries === null ? null : entries.length === 0 ? (
          <p className={layoutStyles.textMuted}>{emptyMessage}</p>
        ) : (
          <div className={styles.list}>
            {entries.map((entry) => {
              const Icon = renderIcon?.(entry) ?? actionIcons?.[entry.action] ?? defaultIcon
              const detail = formatDetail?.(entry)
              return (
                <div key={entry.id} className={styles.item}>
                  <span className={styles.icon}>
                    <Icon size={15} stroke={1.8} />
                  </span>
                  <span className={styles.main}>
                    <span className={styles.label}>{actionLabels[entry.action] ?? entry.action}</span>
                    {detail && <span className={styles.detail}>{detail}</span>}
                    <span className={styles.author}>{entry.user_name ?? 'Неизвестный пользователь'}</span>
                  </span>
                  <span className={styles.time}>
                    {new Date(entry.created_at).toLocaleString('ru-RU', {
                      day: 'numeric',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
              )
            })}
          </div>
        ))}
    </div>
  )
}
