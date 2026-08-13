import { useEffect, useState } from 'react'
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
        <div className="grid-stats">
          <Stat label="Продаж" value={String(dashboard.today.sales_count)} />
          <Stat label="Выручка" value={`${dashboard.today.revenue} ₽`} />
          <Stat label="Прибыль" value={`${dashboard.today.profit} ₽`} />
        </div>
      </div>

      <div className="stack">
        <h3>Неделя</h3>
        <div className="grid-stats">
          <Stat label="Продаж" value={String(dashboard.week.sales_count)} />
          <Stat label="Выручка" value={`${dashboard.week.revenue} ₽`} />
          <Stat label="Прибыль" value={`${dashboard.week.profit} ₽`} />
        </div>
      </div>

      <div className="stack">
        <h3>Месяц</h3>
        <div className="grid-stats">
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
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Товар</th>
                  <th>Продано</th>
                  <th>Выручка</th>
                </tr>
              </thead>
              <tbody>
                {topProducts.map((p) => (
                  <tr key={p.product_id}>
                    <td>{p.product_name}</td>
                    <td>{p.quantity_sold}</td>
                    <td>{p.revenue} ₽</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="stack">
        <h3>Прибыльность по категориям</h3>
        {categoryProfit.length === 0 ? (
          <p className="text-muted">Продаж за месяц пока нет</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Категория</th>
                  <th>Выручка</th>
                  <th>Прибыль</th>
                  <th>Маржа</th>
                </tr>
              </thead>
              <tbody>
                {[...categoryProfit]
                  .sort((a, b) => Number(b.profit) - Number(a.profit))
                  .map((c) => (
                    <tr key={c.category_id ?? 'none'}>
                      <td>{c.category_name}</td>
                      <td>{c.revenue} ₽</td>
                      <td>{c.profit} ₽</td>
                      <td>{Number(c.revenue) > 0 ? `${((Number(c.profit) / Number(c.revenue)) * 100).toFixed(1)}%` : '—'}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="stack">
        <h3>Мёртвый остаток (60+ дней)</h3>
        {deadStock.length === 0 ? (
          <p className="text-muted">Залежавшихся товаров нет</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Товар</th>
                  <th>Остаток</th>
                  <th>Последняя продажа</th>
                </tr>
              </thead>
              <tbody>
                {deadStock.map((d) => (
                  <tr key={d.product_id}>
                    <td>{d.product_name}</td>
                    <td>{formatQuantity(d.quantity)}</td>
                    <td>{d.last_sale_at ? new Date(d.last_sale_at).toLocaleDateString('ru-RU') : 'никогда'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  )
}
