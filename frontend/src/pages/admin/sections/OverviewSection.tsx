import { useCallback, useEffect, useState } from 'react'
import { getAdminOverview, type AdminOverview } from '../../../entities/admin/api'
import { formatCount, formatMoney } from '../../../shared/lib/format'
import { useAutoRefresh, type AdminPeriod } from '../AdminLayout'
import { handleAdminError } from '../shared'
import { BlockError, Card, Metric, MetricRow, Skeleton } from '../ui'
import { TimeSeriesChart } from '../TimeSeriesChart'
import styles from './OverviewSection.module.css'

interface SectionProps {
  logout: () => void
  refreshKey: number
  onLoaded: () => void
  period: AdminPeriod
}

export function OverviewSection({ logout, refreshKey, onLoaded }: SectionProps) {
  const [data, setData] = useState<AdminOverview | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setData(await getAdminOverview())
      setError(null)
    } catch (err) {
      setError(handleAdminError(err, logout))
    } finally {
      onLoaded()
    }
  }, [logout, onLoaded])

  useEffect(() => {
    load()
  }, [load, refreshKey])

  useAutoRefresh(load)

  if (error && !data) {
    return (
      <Card>
        <BlockError message={error} onRetry={load} />
      </Card>
    )
  }

  if (!data) {
    return (
      <div className={styles.loading}>
        <MetricRow>
          <Skeleton height={122} />
          <Skeleton height={122} />
          <Skeleton height={122} />
          <Skeleton height={122} />
        </MetricRow>
        <Skeleton height={280} />
      </div>
    )
  }

  const activeShare =
    data.shops.total > 0 ? Math.round((data.shops.active_7d / data.shops.total) * 100) : 0

  return (
    <div className={styles.grid}>
      <MetricRow>
        <Metric
          label="Магазины"
          value={formatCount(data.shops.total)}
          note={`${formatCount(data.shops.new_7d)} новых за 7 дней`}
        />
        <Metric
          label="Активны за 7 дней"
          value={formatCount(data.shops.active_7d)}
          note={`${activeShare}% от всех магазинов`}
        />
        <Metric
          label="Продажи за 30 дней"
          value={formatCount(data.sales.d30_count)}
          note={`${formatMoney(data.sales.d30_sum)} ₽`}
        />
        <Metric
          label="Заявки с витрины"
          value={formatCount(data.storefront.requests_7d)}
          note={`${formatCount(data.storefront.accepted_7d)} принято за 7 дней`}
        />
      </MetricRow>

      <Card title="Продажи и активные магазины за 30 дней">
        <TimeSeriesChart
          dates={data.series_30d.date}
          series={[
            { kind: 'bars', label: 'Продажи', values: data.series_30d.sales_count },
            { kind: 'line', label: 'Активные магазины', values: data.series_30d.active_shops },
          ]}
          height={260}
        />
      </Card>
    </div>
  )
}
