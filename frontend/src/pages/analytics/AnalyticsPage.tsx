import { useEffect, useState, type CSSProperties } from 'react'
import {
  getDashboard,
  getTopProducts,
  getCategoryProfit,
  getDeadStock,
  getStockValue,
  type Dashboard,
  type ProductSales,
  type CategoryProfit,
  type DeadStockItem,
  type StockValue,
} from '../../entities/analytics/api'
import { ApiError } from '../../shared/api/client'
import { formatQuantity } from '../../shared/lib/format'

const TOP_PRODUCTS_COLUMNS = '2fr 1fr 1fr'
const CATEGORY_PROFIT_COLUMNS = '1.6fr 1fr 1fr 1fr'
const DEAD_STOCK_COLUMNS = '2fr 1fr 1.2fr'

export function AnalyticsPage() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [topProducts, setTopProducts] = useState<ProductSales[]>([])
  const [categoryProfit, setCategoryProfit] = useState<CategoryProfit[]>([])
  const [deadStock, setDeadStock] = useState<DeadStockItem[]>([])
  const [stockValue, setStockValue] = useState<StockValue | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getDashboard(), getTopProducts(), getCategoryProfit(), getDeadStock(), getStockValue()])
      .then(([d, t, cp, dead, sv]) => {
        setDashboard(d)
        setTopProducts(t)
        setCategoryProfit(cp)
        setDeadStock(dead)
        setStockValue(sv)
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить аналитику')
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-muted">Загрузка…</p>
  if (error) return <p className="error">{error}</p>
  if (!dashboard) return null

  return (
    <div className="stack">
      <h2>Аналитика</h2>

      <div className="stack">
        <h3>Сегодня</h3>
        <div className="card card-full grid-stats">
          <Stat label="Продаж" value={String(dashboard.today.sales_count)} />
          <Stat label="Выручка" value={`${dashboard.today.revenue} ₽`} />
          <Stat label="Прибыль" value={`${dashboard.today.profit} ₽`} />
        </div>
      </div>

      <div className="stack">
        <h3>Неделя</h3>
        <div className="card card-full grid-stats">
          <Stat label="Продаж" value={String(dashboard.week.sales_count)} />
          <Stat label="Выручка" value={`${dashboard.week.revenue} ₽`} />
          <Stat label="Прибыль" value={`${dashboard.week.profit} ₽`} />
        </div>
      </div>

      <div className="stack">
        <h3>Месяц</h3>
        <div className="card card-full grid-stats">
          <Stat label="Продаж" value={String(dashboard.month.sales_count)} />
          <Stat label="Выручка" value={`${dashboard.month.revenue} ₽`} />
          <Stat label="Прибыль" value={`${dashboard.month.profit} ₽`} />
        </div>
      </div>

      {stockValue && (
        <div className="card card-full">
          <span className="text-muted">Деньги в товаре</span>
          <div className="stat-value">{stockValue.total_value} ₽</div>
        </div>
      )}

      <div className="stack">
        <h3>Топ товаров</h3>
        {topProducts.length === 0 ? (
          <p className="text-muted">Продаж за месяц пока нет</p>
        ) : (
          <div className="data-table">
            <div className="data-table-head" style={{ gridTemplateColumns: TOP_PRODUCTS_COLUMNS }}>
              <span>Товар</span>
              <span>Продано</span>
              <span>Выручка</span>
            </div>
            <div className="data-table-body">
              {topProducts.map((p, i) => (
                <div
                  key={p.product_id}
                  className="data-row sale-history-row-in"
                  style={
                    {
                      gridTemplateColumns: TOP_PRODUCTS_COLUMNS,
                      '--row-delay': `${Math.min(i, 12) * 25}ms`,
                    } as CSSProperties
                  }
                >
                  <span className="data-row-name">{p.product_name}</span>
                  <span>{p.quantity_sold}</span>
                  <span>{p.revenue} ₽</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="stack">
        <h3>Прибыльность по категориям</h3>
        {categoryProfit.length === 0 ? (
          <p className="text-muted">Продаж за месяц пока нет</p>
        ) : (
          <div className="data-table">
            <div className="data-table-head" style={{ gridTemplateColumns: CATEGORY_PROFIT_COLUMNS }}>
              <span>Категория</span>
              <span>Выручка</span>
              <span>Прибыль</span>
              <span>Маржа</span>
            </div>
            <div className="data-table-body">
              {[...categoryProfit]
                .sort((a, b) => Number(b.profit) - Number(a.profit))
                .map((c, i) => (
                  <div
                    key={c.category_id ?? 'none'}
                    className="data-row sale-history-row-in"
                    style={
                      {
                        gridTemplateColumns: CATEGORY_PROFIT_COLUMNS,
                        '--row-delay': `${Math.min(i, 12) * 25}ms`,
                      } as CSSProperties
                    }
                  >
                    <span className="data-row-name">{c.category_name}</span>
                    <span>{c.revenue} ₽</span>
                    <span>{c.profit} ₽</span>
                    <span>
                      {Number(c.revenue) > 0
                        ? `${((Number(c.profit) / Number(c.revenue)) * 100).toFixed(1)}%`
                        : '—'}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>

      <div className="stack">
        <h3>Мёртвый остаток (60+ дней)</h3>
        {deadStock.length === 0 ? (
          <p className="text-muted">Залежавшихся товаров нет</p>
        ) : (
          <div className="data-table">
            <div className="data-table-head" style={{ gridTemplateColumns: DEAD_STOCK_COLUMNS }}>
              <span>Товар</span>
              <span>Остаток</span>
              <span>Последняя продажа</span>
            </div>
            <div className="data-table-body">
              {deadStock.map((d, i) => (
                <div
                  key={d.product_id}
                  className="data-row sale-history-row-in"
                  style={
                    {
                      gridTemplateColumns: DEAD_STOCK_COLUMNS,
                      '--row-delay': `${Math.min(i, 12) * 25}ms`,
                    } as CSSProperties
                  }
                >
                  <span className="data-row-name">{d.product_name}</span>
                  <span>{formatQuantity(d.quantity)}</span>
                  <span className="text-muted">
                    {d.last_sale_at ? new Date(d.last_sale_at).toLocaleDateString('ru-RU') : 'никогда'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}
