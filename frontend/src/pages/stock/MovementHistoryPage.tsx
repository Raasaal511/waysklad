import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  listDocuments,
  listWarehouses,
  exportDocuments,
  type DocumentHistoryEntry,
  type ExportFormat,
  type Warehouse,
} from '../../entities/inventory/api'
import { listAllProducts, listUnits, type Product, type Unit } from '../../entities/product/api'
import { listEmployees } from '../../entities/profile/api'
import type { User } from '../../entities/auth/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { DropdownMenu } from '../../shared/ui/DropdownMenu'
import { ResetFiltersButton } from '../../shared/ui/ResetFiltersButton'
import { formatQuantity, formatMoney } from '../../shared/lib/format'
import { IconChevronLeft, IconDownload, IconChevronDown } from '@tabler/icons-react'

const MODE_LABELS: Record<DocumentHistoryEntry['type'], string> = {
  receipt: 'Приёмка',
  write_off: 'Списание',
  transfer: 'Перемещение',
  stocktake: 'Инвентаризация',
}

const EXPORT_FORMAT_LABELS: Record<ExportFormat, string> = {
  xlsx: 'Excel (.xlsx)',
  csv: 'CSV (.csv)',
  pdf: 'PDF (.pdf)',
}

type PeriodFilter = 'today' | 'week' | 'month' | 'all'

const PERIOD_LABELS: Record<PeriodFilter, string> = {
  all: 'Всё',
  month: 'Месяц',
  week: 'Неделя',
  today: 'День',
}

function isWithinPeriod(dateStr: string, period: PeriodFilter): boolean {
  if (period === 'all') return true
  const date = new Date(dateStr)
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  if (period === 'today') return date >= startOfToday
  if (period === 'week') {
    const weekAgo = new Date(startOfToday)
    weekAgo.setDate(weekAgo.getDate() - 6)
    return date >= weekAgo
  }
  const monthAgo = new Date(startOfToday)
  monthAgo.setDate(monthAgo.getDate() - 29)
  return date >= monthAgo
}

async function downloadExport(format: ExportFormat) {
  const blob = await exportDocuments(format)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `ostatki.${format}`
  link.click()
  URL.revokeObjectURL(url)
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Сумма документа деньгами — есть только у приёмки (закупочная цена по строкам); для
 * остальных типов операций документ денег не считает, это просто движение количества. */
function documentTotal(doc: DocumentHistoryEntry): number | null {
  if (doc.type !== 'receipt') return null
  const total = doc.lines.reduce((sum, line) => sum + Number(line.quantity) * Number(line.cost ?? 0), 0)
  return total > 0 ? total : null
}

export function MovementHistoryPage() {
  const { user } = useAuth()
  const canSeeEmployees = user?.role === 'owner' || user?.role === 'manager'

  const [documents, setDocuments] = useState<DocumentHistoryEntry[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [units, setUnits] = useState<Unit[]>([])
  const [employees, setEmployees] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)

  const [warehouseFilter, setWarehouseFilter] = useState<number | 'all'>('all')
  const [typeFilter, setTypeFilter] = useState<DocumentHistoryEntry['type'] | 'all'>('all')
  const [period, setPeriod] = useState<PeriodFilter>('all')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const [docs, w, p, u, emp] = await Promise.all([
        listDocuments(),
        listWarehouses(),
        listAllProducts(),
        listUnits(),
        canSeeEmployees ? listEmployees() : Promise.resolve<User[]>([]),
      ])
      setDocuments(docs)
      setWarehouses(w)
      setProducts(p)
      setUnits(u)
      setEmployees(emp)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить историю')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleExport(format: ExportFormat) {
    setExportError(null)
    try {
      await downloadExport(format)
    } catch (err) {
      setExportError(err instanceof ApiError ? err.message : 'Не удалось выгрузить файл')
    }
  }

  const warehouseName = (id: number) => warehouses.find((w) => w.id === id)?.name ?? `#${id}`
  const productName = (id: number) => products.find((p) => p.id === id)?.name ?? `#${id}`
  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code
  const productUnitCode = (id: number) => products.find((p) => p.id === id)?.unit_code ?? 'pcs'
  const authorName = (id: number) =>
    id === user?.id ? `${user.name} (вы)` : employees.find((e) => e.id === id)?.name ?? `#${id}`

  const filtered = useMemo(() => {
    return documents.filter(
      (d) =>
        (warehouseFilter === 'all' || d.warehouse_id === warehouseFilter || d.to_warehouse_id === warehouseFilter) &&
        (typeFilter === 'all' || d.type === typeFilter) &&
        isWithinPeriod(d.created_at, period),
    )
  }, [documents, warehouseFilter, typeFilter, period])

  const periodReceiptsTotal = useMemo(
    () => filtered.reduce((sum, d) => sum + (documentTotal(d) ?? 0), 0),
    [filtered],
  )

  const activeFilterCount =
    (warehouseFilter !== 'all' ? 1 : 0) + (typeFilter !== 'all' ? 1 : 0) + (period !== 'all' ? 1 : 0)

  return (
    <div className="stack">
      <Link to="/stock" className="back-link">
        <IconChevronLeft size={16} stroke={1.8} /> Остатки
      </Link>

      <div className="section-title">
        <h2>История движения товара</h2>
        <DropdownMenu
          align="right"
          trigger={
            <Button variant="secondary">
              <IconDownload size={16} stroke={1.8} /> Экспорт <IconChevronDown size={14} stroke={1.8} />
            </Button>
          }
          items={(Object.keys(EXPORT_FORMAT_LABELS) as ExportFormat[]).map((format) => ({
            key: format,
            label: EXPORT_FORMAT_LABELS[format],
            onSelect: () => handleExport(format),
          }))}
        />
      </div>
      {exportError && <p className="error">{exportError}</p>}

      <div className="sale-period-tabs">
        {(Object.keys(PERIOD_LABELS) as PeriodFilter[]).map((p) => (
          <Button
            key={p}
            translate="no"
            variant="secondary"
            active={period === p}
            onClick={() => setPeriod(p)}
          >
            {PERIOD_LABELS[p]}
          </Button>
        ))}
      </div>

      <div className="sale-filters-row">
        {warehouses.length > 1 && (
          <label className="filter-field">
            <Select
              value={warehouseFilter === 'all' ? 'all' : String(warehouseFilter)}
              onChange={(v) => setWarehouseFilter(v === 'all' ? 'all' : Number(v))}
              options={[
                { value: 'all', label: 'Все склады' },
                ...warehouses.map((w) => ({ value: String(w.id), label: w.name })),
              ]}
            />
          </label>
        )}
        <label className="filter-field">
          <Select
            value={typeFilter}
            onChange={(v) => setTypeFilter(v as DocumentHistoryEntry['type'] | 'all')}
            options={[
              { value: 'all', label: 'Все операции' },
              ...(Object.keys(MODE_LABELS) as DocumentHistoryEntry['type'][]).map((t) => ({
                value: t,
                label: MODE_LABELS[t],
              })),
            ]}
          />
        </label>
        {activeFilterCount > 0 && (
          <ResetFiltersButton
            onClick={() => {
              setWarehouseFilter('all')
              setTypeFilter('all')
              setPeriod('all')
            }}
          />
        )}
      </div>

      {!loading && filtered.length > 0 && periodReceiptsTotal > 0 && (
        <div className="card card-full sale-period-summary">
          <h3 className="sale-period-summary-title">Закуплено за «{PERIOD_LABELS[period]}»</h3>
          <div className="stat">
            <span className="stat-label">Сумма приёмок</span>
            <span className="stat-value movement-history-money">{formatMoney(periodReceiptsTotal)} ₽</span>
          </div>
        </div>
      )}

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : filtered.length === 0 ? (
        <p className="text-muted">
          {documents.length === 0 ? 'Движений товара пока не было' : 'По этим фильтрам ничего не найдено'}
        </p>
      ) : (
        <div className="stack" style={{ gap: 10 }}>
          {filtered.map((doc) => {
            const expanded = expandedId === doc.id
            const total = documentTotal(doc)
            return (
              <div key={doc.id} className="card card-full stack" style={{ gap: 10 }}>
                <button
                  type="button"
                  className="movement-history-summary"
                  aria-expanded={expanded}
                  onClick={() => setExpandedId(expanded ? null : doc.id)}
                >
                  <div className="stack" style={{ gap: 4, flex: 1 }}>
                    <div className="row wrap" style={{ gap: 8 }}>
                      <span className="badge accent">{MODE_LABELS[doc.type]}</span>
                      <span className="text-muted">№{doc.number}</span>
                      <span className="text-muted">{formatDateTime(doc.created_at)}</span>
                    </div>
                    <div className="row wrap" style={{ gap: 16 }}>
                      <span>
                        {doc.type === 'transfer'
                          ? `${warehouseName(doc.warehouse_id)} → ${doc.to_warehouse_id ? warehouseName(doc.to_warehouse_id) : ''}`
                          : warehouseName(doc.warehouse_id)}
                      </span>
                      <span className="text-muted">{authorName(doc.author_id)}</span>
                      <span className="text-muted">
                        {doc.lines.length} {doc.lines.length === 1 ? 'позиция' : 'позиций'}
                      </span>
                    </div>
                  </div>
                  {total !== null && (
                    <span className="movement-history-money">{formatMoney(total)} ₽</span>
                  )}
                  <IconChevronDown size={18} stroke={1.8} className="disclosure-chevron" />
                </button>

                {expanded && (
                  <>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Товар</th>
                            <th>Кол-во</th>
                            {doc.type === 'receipt' && <th>Закуп. цена</th>}
                          </tr>
                        </thead>
                        <tbody>
                          {doc.lines.map((line, i) => (
                            <tr key={i}>
                              <td>{productName(line.product_id)}</td>
                              <td>
                                {formatQuantity(line.quantity)} {unitName(productUnitCode(line.product_id))}
                              </td>
                              {doc.type === 'receipt' && (
                                <td className="movement-history-money">
                                  {line.cost ? `${formatMoney(line.cost)} ₽` : '—'}
                                </td>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {doc.note && <span className="text-muted">{doc.note}</span>}
                  </>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
