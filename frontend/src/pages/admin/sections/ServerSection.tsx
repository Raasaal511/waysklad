/**
 * Раздел «Сервер». Пока перенесён из прежней единой страницы без изменений —
 * редизайн метрик и блоков эксплуатации идёт отдельным шагом (B5).
 */
import { useCallback, useEffect, useState } from 'react'
import { getAdminStatus, type AdminMetricsPoint, type AdminStatus } from '../../../entities/admin/api'
import layoutStyles from '../../../shared/ui/Layout.module.css'
import { handleAdminError } from '../shared'
import styles from '../AdminPage.module.css'

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

interface SectionProps {
  logout: () => void
  refreshKey: number
  onLoaded: () => void
}

export function ServerSection({ logout, refreshKey, onLoaded }: SectionProps) {
  const [status, setStatus] = useState<AdminStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setStatus(await getAdminStatus())
      setError(null)
    } catch (err) {
      setError(handleAdminError(err, logout))
    } finally {
      onLoaded()
    }
  }, [logout, onLoaded])

  useEffect(() => {
    load()
    const id = window.setInterval(load, 8000)
    return () => window.clearInterval(id)
  }, [load, refreshKey])

  if (error) return <p className={layoutStyles.error}>{error}</p>
  if (!status) return <p className={layoutStyles.textMuted}>Загрузка…</p>

  return (
    <div className={styles.statusLayout}>
      <section className={styles.gaugeRow}>
        <GaugeCard label="Процессор" percent={status.cpu_percent} />
        <GaugeCard
          label="Память"
          percent={status.memory_percent}
          note={`${formatMb(status.memory_used_mb)} из ${formatMb(status.memory_total_mb)}`}
        />
        <GaugeCard
          label="Диск"
          percent={status.disk_percent}
          note={`${status.disk_used_gb} ГБ из ${status.disk_total_gb} ГБ`}
        />
      </section>

      {status.history.length > 1 && (
        <section className={styles.historyCard}>
          <div className={styles.historyHead}>
            <span className={styles.cardLabel}>Нагрузка за последний час</span>
            <div className={styles.historyLegend}>
              <span className={styles.legendDot} data-series="cpu" />
              CPU
              <span className={styles.legendDot} data-series="memory" />
              Память
            </div>
          </div>
          <HistoryChart points={status.history} />
        </section>
      )}

      <section className={styles.pillRow}>
        <HealthPill label="База данных" ok={status.db_connected} />
        <HealthPill label="Redis" ok={status.redis_connected} />
      </section>

      <section className={styles.grid}>
        <StatusCard label="Пользователи" value={String(status.active_users)} />
        <StatusCard label="Магазины" value={String(status.active_tenants)} />
        <StatusCard
          label="Онлайн сейчас"
          value={String(status.online_now)}
          note={status.online_now_note}
        />
      </section>

      {status.recent_tenants.length > 0 && (
        <section>
          <h3 className={styles.sectionTitle}>Недавно зарегистрированные магазины</h3>
          <ul className={styles.recentList}>
            {status.recent_tenants.map((t) => (
              <li key={t.id} className={styles.recentItem}>
                <Link to={`/admin/tenants/${t.id}`} className={styles.recentName}>
                  {t.name}
                </Link>
                <span className={styles.recentSlug}>{t.slug ?? '—'}</span>
                <time className={styles.recentTime}>{formatDateTime(t.created_at)}</time>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

function HistoryChart({ points }: { points: AdminMetricsPoint[] }) {
  const width = 600
  const height = 80
  const pad = 4

  function toPath(values: number[]): string {
    if (values.length < 2) return ''
    const step = (width - pad * 2) / (values.length - 1)
    return values
      .map((v, i) => {
        const x = pad + i * step
        const y = height - pad - (Math.min(Math.max(v, 0), 100) / 100) * (height - pad * 2)
        return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  }

  const cpuPath = toPath(points.map((p) => p.cpu_percent))
  const memPath = toPath(points.map((p) => p.memory_percent))

  return (
    <svg
      className={styles.historyChart}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="График нагрузки CPU и памяти за последний час"
    >
      <path d={memPath} className={styles.historyLineMemory} fill="none" />
      <path d={cpuPath} className={styles.historyLineCpu} fill="none" />
    </svg>
  )
}

function HealthPill({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className={styles.healthPill} data-ok={ok}>
      <span className={styles.healthDot} />
      <span>{label}</span>
      <strong>{ok ? 'в норме' : 'недоступен'}</strong>
    </div>
  )
}

function formatMb(mb: number): string {
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} ГБ` : `${mb} МБ`
}

function gaugeLevel(percent: number): 'ok' | 'warn' | 'danger' {
  if (percent >= 90) return 'danger'
  if (percent >= 70) return 'warn'
  return 'ok'
}

function GaugeCard({ label, percent, note }: { label: string; percent: number; note?: string }) {
  const level = gaugeLevel(percent)
  return (
    <div className={styles.gaugeCard} data-level={level}>
      <div className={styles.gaugeHead}>
        <span className={styles.cardLabel}>{label}</span>
        <span className={styles.gaugeValue}>{percent.toFixed(0)}%</span>
      </div>
      <div className={styles.gaugeTrack}>
        <div
          className={styles.gaugeFill}
          data-level={level}
          style={{ width: `${Math.min(Math.max(percent, 0), 100)}%` }}
        />
      </div>
      {note && <span className={styles.note}>{note}</span>}
    </div>
  )
}

function StatusCard({
  label,
  value,
  ok,
  note,
}: {
  label: string
  value: string
  ok?: boolean
  note?: string
}) {
  return (
    <div className={styles.card}>
      <span className={styles.cardLabel}>{label}</span>
      <strong className={ok === false ? styles.bad : undefined}>{value}</strong>
      {note && <span className={styles.note} title={note}>{note}</span>}
    </div>
  )
}

type TenantStatusFilter = 'all' | 'active' | 'suspended'
