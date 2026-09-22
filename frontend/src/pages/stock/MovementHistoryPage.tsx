import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { listDocuments, getDocument, exportDocuments, type DocumentHistoryEntry, type ExportFormat } from '../../entities/inventory/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { useCatalog } from '../../app/CatalogContext'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { DropdownMenu } from '../../shared/ui/DropdownMenu'
import { ResetFiltersButton } from '../../shared/ui/ResetFiltersButton'
import { PillTabs } from '../../shared/ui/PillTabs'
import { formatQuantity, formatMoney } from '../../shared/lib/format'
import { IconChevronLeft, IconDownload, IconChevronDown, IconDots } from '@tabler/icons-react'
import { IconButton } from '../../shared/ui/IconButton'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './MovementHistoryPage.module.css'

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
  const [searchParams, setSearchParams] = useSearchParams()

  const { warehouses, products, units, employees, ensureWarehouses, ensureProducts, ensureUnits, ensureEmployees } =
    useCatalog()
  const [documents, setDocuments] = useState<DocumentHistoryEntry[]>([])
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
      const [docs] = await Promise.all([
        listDocuments(),
        ensureWarehouses(),
        ensureProducts(),
        ensureUnits(),
        canSeeEmployees ? ensureEmployees() : Promise.resolve(),
      ])
      setDocuments(docs)
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

  // ?open=id — точечная загрузка документа (из уведомления/ссылки)
  useEffect(() => {
    const openId = searchParams.get('open')
    if (!openId) return
    const id = Number(openId)
    if (!Number.isFinite(id)) return
    getDocument(id)
      .then((doc) => {
        setDocuments((prev) => (prev.some((d) => d.id === doc.id) ? prev : [doc, ...prev]))
        setExpandedId(doc.id)
      })
      .catch(() => {})
      .finally(() => {
        setSearchParams(
          (prev) => {
            const next = new URLSearchParams(prev)
            next.delete('open')
            return next
          },
          { replace: true },
        )
      })
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
    <div className={layoutStyles.stack}>
      <Link to="/stock" className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> Склады
      </Link>

      <div className={layoutStyles.sectionTitle}>
        <h2>История движения товара</h2>
        <div className={layoutStyles.pageTitleActions}>
          <div className={layoutStyles.pageTitleActionsDesktop}>
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
          <div className={layoutStyles.pageTitleActionsMobile}>
            <DropdownMenu
              align="right"
              trigger={
                <IconButton variant="muted" size="lg" aria-label="Экспорт">
                  <IconDots size={20} stroke={1.8} />
                </IconButton>
              }
              items={(Object.keys(EXPORT_FORMAT_LABELS) as ExportFormat[]).map((format) => ({
                key: format,
                label: `Экспорт: ${EXPORT_FORMAT_LABELS[format]}`,
                onSelect: () => handleExport(format),
              }))}
            />
          </div>
        </div>
      </div>
      {exportError && <p className={layoutStyles.error}>{exportError}</p>}

      <PillTabs
        value={period}
        options={Object.keys(PERIOD_LABELS) as PeriodFilter[]}
        labels={PERIOD_LABELS}
        onChange={setPeriod}
      />

      <div className={[layoutStyles.row, layoutStyles.wrap].join(' ')} style={{ gap: 14, alignItems: 'end' }}>
        {warehouses.length > 1 && (
          <label className={layoutStyles.filterField}>
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
        <label className={layoutStyles.filterField}>
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
        <div className={[layoutStyles.card, layoutStyles.cardFull, layoutStyles.stack].join(' ')} style={{ gap: 18 }}>
          <h3 className={styles['period-summary-title']}>Закуплено за «{PERIOD_LABELS[period]}»</h3>
          <div className={layoutStyles.stat}>
            <span className={layoutStyles.statLabel}>Сумма приёмок</span>
            <span className={`${layoutStyles.statValue} ${styles['movement-history-money']}`}>
              {formatMoney(periodReceiptsTotal)} ₽
            </span>
          </div>
        </div>
      )}

      {error && <p className={layoutStyles.error}>{error}</p>}
      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : filtered.length === 0 ? (
        <p className={layoutStyles.textMuted}>
          {documents.length === 0 ? 'Движений товара пока не было' : 'По этим фильтрам ничего не найдено'}
        </p>
      ) : (
        <div className={layoutStyles.stack} style={{ gap: 10 }}>
          {filtered.map((doc, i) => {
            const expanded = expandedId === doc.id
            const total = documentTotal(doc)
            return (
              <div
                key={doc.id}
                className={[layoutStyles.card, layoutStyles.cardFull, layoutStyles.stack, 'sale-history-row-in'].join(
                  ' ',
                )}
                style={{ gap: 10, '--row-delay': `${Math.min(i, 12) * 25}ms` } as CSSProperties}
              >
                <button
                  type="button"
                  className={styles['movement-history-summary']}
                  aria-expanded={expanded}
                  onClick={() => setExpandedId(expanded ? null : doc.id)}
                >
                  <div className={layoutStyles.stack} style={{ gap: 4, flex: 1 }}>
                    <div className={[layoutStyles.row, layoutStyles.wrap].join(' ')} style={{ gap: 8 }}>
                      <span className="badge accent">
                        {MODE_LABELS[doc.type]}
                      </span>
                      <span className={layoutStyles.textMuted}>№{doc.number}</span>
                      <span className={layoutStyles.textMuted}>{formatDateTime(doc.created_at)}</span>
                    </div>
                    <div className={[layoutStyles.row, layoutStyles.wrap].join(' ')} style={{ gap: 16 }}>
                      <span>
                        {doc.type === 'transfer'
                          ? `${warehouseName(doc.warehouse_id)} → ${doc.to_warehouse_id ? warehouseName(doc.to_warehouse_id) : ''}`
                          : warehouseName(doc.warehouse_id)}
                      </span>
                      <span className={layoutStyles.textMuted}>{authorName(doc.author_id)}</span>
                      <span className={layoutStyles.textMuted}>
                        {doc.lines.length} {doc.lines.length === 1 ? 'позиция' : 'позиций'}
                      </span>
                    </div>
                  </div>
                  {total !== null && (
                    <span className={styles['movement-history-money']}>{formatMoney(total)} ₽</span>
                  )}
                  <IconChevronDown size={18} stroke={1.8} className={styles['disclosure-chevron']} />
                </button>

                {expanded && (
                  <>
                    <div className={layoutStyles.dataTable}>
                      <div
                        className={layoutStyles.dataTableHead}
                        style={{ gridTemplateColumns: doc.type === 'receipt' ? '2fr 1fr 1fr' : '2fr 1fr' }}
                      >
                        <span>Товар</span>
                        <span>Кол-во</span>
                        {doc.type === 'receipt' && <span>Закуп. цена</span>}
                      </div>
                      <div className={layoutStyles.dataTableBody}>
                        {doc.lines.map((line, i) => (
                          <div
                            key={i}
                            className={layoutStyles.dataRow}
                            style={{ gridTemplateColumns: doc.type === 'receipt' ? '2fr 1fr 1fr' : '2fr 1fr' }}
                          >
                            <span className={layoutStyles.dataRowName}>{productName(line.product_id)}</span>
                            <span>
                              {formatQuantity(line.quantity)} {unitName(productUnitCode(line.product_id))}
                            </span>
                            {doc.type === 'receipt' && (
                              <span className={styles['movement-history-money']}>
                                {line.cost ? `${formatMoney(line.cost)} ₽` : '—'}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                    {doc.note && <span className={layoutStyles.textMuted}>{doc.note}</span>}
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
