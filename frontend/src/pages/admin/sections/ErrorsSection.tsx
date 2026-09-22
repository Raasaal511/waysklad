/**
 * Раздел «Ошибки». Перенесён из прежней страницы; группировка и пометка
 * «решено» — следующий шаг (B6).
 */
import { useCallback, useEffect, useState } from 'react'
import { getAdminErrorLogs, type AdminErrorLog } from '../../../entities/admin/api'
import layoutStyles from '../../../shared/ui/Layout.module.css'
import { handleAdminError } from '../shared'
import styles from '../AdminPage.module.css'

interface SectionProps {
  logout: () => void
  refreshKey: number
  onLoaded: () => void
}

export function ErrorsSection({ logout, refreshKey, onLoaded }: SectionProps) {
  const [errors, setErrors] = useState<AdminErrorLog[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [methodFilter, setMethodFilter] = useState<string>('all')
  const [expandedKey, setExpandedKey] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await getAdminErrorLogs(200)
      setErrors(data.errors)
      setError(null)
    } catch (err) {
      setError(handleAdminError(err, logout))
    } finally {
      setLoading(false)
      onLoaded()
    }
  }, [logout, onLoaded])

  useEffect(() => {
    load()
    const id = window.setInterval(load, ERROR_AUTO_REFRESH_MS)
    return () => window.clearInterval(id)
  }, [load, refreshKey])

  if (loading) return <p className={layoutStyles.textMuted}>Загрузка…</p>
  if (error) return <p className={layoutStyles.error}>{error}</p>

  const methods = Array.from(new Set(errors.map((e) => e.method))).sort()
  const normalizedQuery = query.trim().toLowerCase()
  const filtered = errors.filter((e) => {
    if (methodFilter !== 'all' && e.method !== methodFilter) return false
    if (!normalizedQuery) return true
    return (
      e.path.toLowerCase().includes(normalizedQuery) ||
      e.message.toLowerCase().includes(normalizedQuery) ||
      e.error_type.toLowerCase().includes(normalizedQuery)
    )
  })

  return (
    <div className={styles.errorsLayout}>
      <div className={styles.errorsToolbar}>
        <input
          type="search"
          className={styles.searchInput}
          placeholder="Поиск по пути, типу или тексту ошибки…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {methods.length > 1 && (
          <div className={styles.filterTabs}>
            <FilterTab active={methodFilter === 'all'} onClick={() => setMethodFilter('all')}>
              Все · {errors.length}
            </FilterTab>
            {methods.map((m) => (
              <FilterTab key={m} active={methodFilter === m} onClick={() => setMethodFilter(m)}>
                {m} · {errors.filter((e) => e.method === m).length}
              </FilterTab>
            ))}
          </div>
        )}
      </div>

      {errors.length === 0 ? (
        <p className={layoutStyles.textMuted}>Пока нет записанных ошибок</p>
      ) : filtered.length === 0 ? (
        <p className={layoutStyles.textMuted}>Ничего не найдено</p>
      ) : (
        <ul className={styles.errorList}>
          {filtered.map((e, i) => {
            const key = `${e.timestamp}-${i}`
            const expanded = expandedKey === key
            return (
              <li key={key} className={styles.errorItem} data-expanded={expanded}>
                <button
                  type="button"
                  className={styles.errorRow}
                  onClick={() => setExpandedKey(expanded ? null : key)}
                  aria-expanded={expanded}
                >
                  <time className={styles.errorTime}>{formatLogTime(e.timestamp)}</time>
                  <span className={styles.errorMethod}>{e.method}</span>
                  <span className={styles.errorType}>{e.error_type}</span>
                  <span className={styles.errorLine}>
                    <span className={styles.errorPath}>{e.path}</span>
                    {' — '}
                    <span className={styles.errorMessage}>{e.message}</span>
                  </span>
                </button>
                {expanded && (
                  <div className={styles.errorDetail}>
                    <div>
                      <span className={styles.errorDetailLabel}>Время</span>
                      <span>{new Date(e.timestamp).toLocaleString('ru-RU')}</span>
                    </div>
                    <div>
                      <span className={styles.errorDetailLabel}>Запрос</span>
                      <code>
                        {e.method} {e.path}
                      </code>
                    </div>
                    <div>
                      <span className={styles.errorDetailLabel}>Тип</span>
                      <span>{e.error_type}</span>
                    </div>
                    <div>
                      <span className={styles.errorDetailLabel}>Сообщение</span>
                      <span className={styles.errorDetailMessage}>{e.message}</span>
                    </div>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

function formatLogTime(value: string): string {
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
