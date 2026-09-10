import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  listActiveDebts,
  listClosedDebts,
  getDebtsOverview,
  listDueDebts,
  type Debt,
  type DebtsOverview,
} from '../../entities/debt/api'
import { searchClients, type Client } from '../../entities/counterparty/api'
import { useCatalog } from '../../app/CatalogContext'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import {
  IconPlus,
  IconChevronRight,
  IconUser,
  IconTruck,
  IconArrowUpRight,
  IconArrowDownLeft,
  IconCalendarRepeat,
  IconSearch,
  IconClockHour4,
  IconBrandWhatsapp,
} from '@tabler/icons-react'
import { Button } from '../../shared/ui/Button'
import { formatMoney } from '../../shared/lib/format'
import { DEBT_STATUS_BADGE_CLASS, DEBT_STATUS_LABELS } from '../../entities/debt/debtStatus'
import { daysOverdue, pluralDays } from '../../entities/debt/dueDate'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './DebtsPage.module.css'

// Цвет левой полоски карточки долга — тот же смысл, что у бейджа статуса,
// но как акцент, по которому можно опознать "горящий" долг не читая текст.
const DEBT_STATUS_ACCENT: Record<Debt['status'], string> = {
  active: 'var(--border)',
  due_soon: 'var(--warning)',
  overdue: 'var(--danger)',
  partially_paid: 'var(--warning)',
  closed: 'var(--accent)',
}

const STATUS_FILTERS: { value: Debt['status'] | 'all'; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'overdue', label: 'Просрочен' },
  { value: 'due_soon', label: 'Скоро срок' },
  { value: 'partially_paid', label: 'Погашен частично' },
  { value: 'active', label: 'Активен' },
]

// Дата, которой считаем долг закрытым — последняя оплата (если она была);
// нужна только для группировки погашённых долгов по месяцу на отдельной
// вкладке, в данных нет отдельного closed_at.
function closedOn(debt: Debt): string {
  if (debt.repayments.length === 0) return debt.issued_at
  return debt.repayments.reduce((latest, r) => (r.on > latest ? r.on : latest), debt.repayments[0].on)
}

function monthLabel(dateStr: string): string {
  const label = new Date(dateStr).toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
  return label.charAt(0).toUpperCase() + label.slice(1)
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString('ru-RU')
}

const PAGE_SIZE = 50

const DEBTS_VIEW_KEY = 'debts_view'
const DEBTS_DIRECTION_KEY = 'debts_direction'
const DEBTS_STATUS_FILTER_KEY = 'debts_status_filter'
const DEBT_STATUS_VALUES: (Debt['status'] | 'all')[] = [
  'all',
  'active',
  'due_soon',
  'overdue',
  'partially_paid',
  'closed',
]

export function DebtsPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const highlightId = searchParams.get('highlight')
  const [debts, setDebts] = useState<Debt[]>([])
  const [total, setTotal] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [closedDebts, setClosedDebts] = useState<Debt[]>([])
  const [closedTotal, setClosedTotal] = useState(0)
  const [closedLoaded, setClosedLoaded] = useState(false)
  const [loadingClosed, setLoadingClosed] = useState(false)
  const { suppliers, ensureSuppliers } = useCatalog()
  const [clients, setClients] = useState<Client[]>([])
  const [overview, setOverview] = useState<DebtsOverview | null>(null)
  const [whatsappByDebtId, setWhatsappByDebtId] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showUpcoming, setShowUpcoming] = useState(false)
  // Вкладки/фильтр просмотра — предпочтение устройства, переживает обновление страницы.
  const [view, setView] = useState<'active' | 'closed'>(
    () => (localStorage.getItem(DEBTS_VIEW_KEY) === 'closed' ? 'closed' : 'active'),
  )
  const [direction, setDirection] = useState<'clients' | 'suppliers'>(
    () => (localStorage.getItem(DEBTS_DIRECTION_KEY) === 'suppliers' ? 'suppliers' : 'clients'),
  )
  const [statusFilter, setStatusFilter] = useState<Debt['status'] | 'all'>(() => {
    const saved = localStorage.getItem(DEBTS_STATUS_FILTER_KEY)
    return saved && (DEBT_STATUS_VALUES as string[]).includes(saved) ? (saved as Debt['status'] | 'all') : 'all'
  })

  useEffect(() => {
    localStorage.setItem(DEBTS_VIEW_KEY, view)
  }, [view])
  useEffect(() => {
    localStorage.setItem(DEBTS_DIRECTION_KEY, direction)
  }, [direction])
  useEffect(() => {
    localStorage.setItem(DEBTS_STATUS_FILTER_KEY, statusFilter)
  }, [statusFilter])
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(timer)
  }, [query])

  function refreshOverview() {
    getDebtsOverview().then(setOverview).catch(() => {})
    listDueDebts()
      .then((due) => {
        const map: Record<number, string> = {}
        for (const d of due) {
          if (d.whatsapp_reminder_link) map[d.id] = d.whatsapp_reminder_link
        }
        setWhatsappByDebtId(map)
      })
      .catch(() => {})
  }

  // Первая загрузка страницы — полноэкранный "Загрузка…", заодно тянет
  // клиентов/поставщиков. Смена фильтра ими не пользуется — см. reloadDebts.
  async function load() {
    setLoading(true)
    try {
      const [{ items, total: t }, clientList] = await Promise.all([
        listActiveDebts({ direction, status: statusFilter, query: debouncedQuery, limit: PAGE_SIZE }),
        searchClients(),
        ensureSuppliers(),
      ])
      setDebts(items)
      setTotal(t)
      setClients(clientList)
      refreshOverview()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить долги')
    } finally {
      setLoading(false)
    }
  }

  const isFirstLoad = useRef(true)

  // Перезагрузка списка при смене фильтра — без полноэкранного "Загрузка…" и
  // без повторных запросов клиентов/поставщиков.
  async function reloadDebts() {
    try {
      const { items, total: t } = await listActiveDebts({
        direction, status: statusFilter, query: debouncedQuery, limit: PAGE_SIZE,
      })
      setDebts(items)
      setTotal(t)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить долги')
    }
  }

  async function loadMore() {
    setLoadingMore(true)
    try {
      const { items, total: t } = await listActiveDebts({
        direction, status: statusFilter, query: debouncedQuery, limit: PAGE_SIZE, offset: debts.length,
      })
      setDebts((prev) => [...prev, ...items])
      setTotal(t)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить долги')
    } finally {
      setLoadingMore(false)
    }
  }

  useEffect(() => {
    if (isFirstLoad.current) {
      isFirstLoad.current = false
      load()
    } else {
      reloadDebts()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [direction, statusFilter, debouncedQuery])

  // Погашенные долги не нужны по умолчанию — грузим только когда владелец
  // действительно открыл вкладку "Погашенные"; при смене поиска перезагружаем.
  useEffect(() => {
    if (view !== 'closed') return
    setLoadingClosed(true)
    listClosedDebts({ direction, query: debouncedQuery, limit: PAGE_SIZE })
      .then(({ items, total: t }) => {
        setClosedDebts(items)
        setClosedTotal(t)
        setClosedLoaded(true)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Не удалось загрузить погашенные долги'))
      .finally(() => setLoadingClosed(false))
  }, [view, direction, debouncedQuery])

  async function loadMoreClosed() {
    setLoadingClosed(true)
    try {
      const { items, total: t } = await listClosedDebts({
        direction, query: debouncedQuery, limit: PAGE_SIZE, offset: closedDebts.length,
      })
      setClosedDebts((prev) => [...prev, ...items])
      setClosedTotal(t)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить погашенные долги')
    } finally {
      setLoadingClosed(false)
    }
  }

  const counterpartyName = (debt: Debt) =>
    debt.client_id
      ? clients.find((c) => c.id === debt.client_id)?.name ?? `Клиент #${debt.client_id}`
      : suppliers.find((s) => s.id === debt.supplier_id)?.name ?? `Поставщик #${debt.supplier_id}`

  // Сортировка и группировка уже применены сервером (severity/issued_at) —
  // здесь только группировка погашённых по месяцу для отображения.
  const closedGroups = useMemo(() => {
    const groups: { label: string; items: Debt[] }[] = []
    for (const d of closedDebts) {
      const label = monthLabel(closedOn(d))
      const group = groups.at(-1)?.label === label ? groups.at(-1)! : { label, items: [] }
      if (groups.at(-1) !== group) groups.push(group)
      group.items.push(d)
    }
    return groups
  }, [closedDebts])

  const upcoming = overview?.upcoming_payments ?? []
  const totalOwedToUs = Number(overview?.client_total_balance ?? 0)
  const totalWeOwe = Number(overview?.supplier_total_balance ?? 0)
  const clientDebtCount = overview?.client_debt_count ?? 0
  const supplierDebtCount = overview?.supplier_debt_count ?? 0

  // Переход по ссылке "?highlight=id" (из уведомления, из продажи) — сразу
  // открываем карточку конкретного долга.
  useEffect(() => {
    if (!highlightId) return
    navigate(`/debts/${highlightId}`, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlightId])

  return (
    <div className={layoutStyles.stack}>
      <div className={layoutStyles.sectionTitle}>
        <h2>Долги</h2>
        <div className={layoutStyles.row} style={{ gap: 8 }}>
          {overview?.has_scheduled_payments && (
            <Button variant="secondary" onClick={() => setShowUpcoming(true)}>
              <IconClockHour4 size={16} stroke={1.8} /> Выплаты
              {upcoming.length > 0 && <span className={layoutStyles.countBadge}>{upcoming.length}</span>}
            </Button>
          )}
          <Button onClick={() => navigate('/debts/new')}>
            <IconPlus size={16} stroke={1.8} /> Выдать долг
          </Button>
        </div>
      </div>

      {error && <p className={layoutStyles.error}>{error}</p>}

      {showUpcoming && (
        <Modal title="Ближайшие выплаты" size="wide" onClose={() => setShowUpcoming(false)}>
          {upcoming.length === 0 && (
            <p className={layoutStyles.textMuted}>В ближайший месяц выплат нет</p>
          )}
          <div className={`${styles['debt-upcoming-list']} ${styles['debt-upcoming-list-modal']}`}>
            {upcoming.map((p, i) => {
              const overdue = daysOverdue(p.due_date) > 0
              return (
                <button
                  key={i}
                  type="button"
                  className={styles['debt-upcoming-row']}
                  onClick={() => {
                    setShowUpcoming(false)
                    navigate(`/debts/${p.debt_id}`)
                  }}
                >
                  <span
                    className={[styles['debt-upcoming-date'], overdue && layoutStyles.textDanger]
                      .filter(Boolean)
                      .join(' ')}
                  >
                    {formatDate(p.due_date)}
                  </span>
                  <span className={styles['debt-upcoming-name']}>{p.counterparty_name}</span>
                  {overdue && (
                    <span className={`${layoutStyles.textDanger} ${styles['debt-upcoming-overdue']}`}>
                      просрочен на {daysOverdue(p.due_date)} {pluralDays(daysOverdue(p.due_date))}
                    </span>
                  )}
                  <strong className={styles['debt-upcoming-amount']}>{formatMoney(p.amount)} ₽</strong>
                  <IconChevronRight size={16} stroke={1.8} className={layoutStyles.dataRowChevron} />
                </button>
              )
            })}
          </div>
        </Modal>
      )}

      <div className="sale-period-tabs">
        <Button variant="secondary" active={view === 'active'} onClick={() => setView('active')}>
          Активные
        </Button>
        <Button variant="secondary" active={view === 'closed'} onClick={() => setView('closed')}>
          Погашенные
        </Button>
      </div>

      {!loading && view === 'active' && (
        <div className={styles['debt-tabs']}>
          <button
            type="button"
            className={[
              styles['debt-tab'],
              styles['debt-tab-owed-to-us'],
              direction === 'clients' && styles['debt-tab-active'],
            ].filter(Boolean).join(' ')}
            onClick={() => setDirection('clients')}
          >
            <span className={styles['debt-tab-label']}>
              <IconArrowDownLeft size={14} stroke={2} /> Нам должны клиенты
            </span>
            <strong>{formatMoney(String(totalOwedToUs))} ₽</strong>
            {clientDebtCount > 0 && <span className={layoutStyles.countBadge}>{clientDebtCount}</span>}
          </button>
          <button
            type="button"
            className={[
              styles['debt-tab'],
              styles['debt-tab-we-owe'],
              direction === 'suppliers' && styles['debt-tab-active'],
            ].filter(Boolean).join(' ')}
            onClick={() => setDirection('suppliers')}
          >
            <span className={styles['debt-tab-label']}>
              <IconArrowUpRight size={14} stroke={2} /> Мы должны поставщикам
            </span>
            <strong>{formatMoney(String(totalWeOwe))} ₽</strong>
            {supplierDebtCount > 0 && <span className={layoutStyles.countBadge}>{supplierDebtCount}</span>}
          </button>
        </div>
      )}

      {!loading && (
        <div className="sale-search-panel">
          <div className="sale-search-row">
            <IconSearch size={16} stroke={1.8} className="sale-search-icon" />
            <input
              className="sale-search-input"
              placeholder="Поиск по клиенту или поставщику…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>
      )}

      {!loading && view === 'active' && (
        <div className={styles['debt-status-filters']}>
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              className={[
                styles['debt-status-filter'],
                statusFilter === f.value && styles['debt-status-filter-active'],
              ].filter(Boolean).join(' ')}
              onClick={() => setStatusFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
      )}

      {view === 'active' ? (
        loading ? (
          <p className={layoutStyles.textMuted}>Загрузка…</p>
        ) : debts.length === 0 ? (
          <p className={layoutStyles.textMuted}>
            {debouncedQuery.trim()
              ? 'Ничего не найдено'
              : statusFilter === 'all'
                ? 'Долгов нет'
                : 'Долгов с таким статусом нет'}
          </p>
        ) : (
          <div key={`${direction}-${statusFilter}`} className={layoutStyles.stack}>
            <div className={styles['debt-row-list']}>
              {debts.map((d, i) => (
                <DebtRow
                  key={d.id}
                  debt={d}
                  name={counterpartyName(d)}
                  onOpen={() => navigate(`/debts/${d.id}`)}
                  whatsappLink={whatsappByDebtId[d.id]}
                  index={i}
                />
              ))}
            </div>
            {debts.length < total && (
              <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? 'Загрузка…' : `Показать ещё (${total - debts.length})`}
              </Button>
            )}
          </div>
        )
      ) : loadingClosed && !closedLoaded ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : closedGroups.length === 0 ? (
        <p className={layoutStyles.textMuted}>{debouncedQuery.trim() ? 'Ничего не найдено' : 'Погашенных долгов нет'}</p>
      ) : (
        <div className={layoutStyles.stack}>
          {closedGroups.map((group) => (
            <div key={group.label} className={styles['debt-closed-group']}>
              <div className={styles['debt-closed-group-head']}>
                <span>{group.label}</span>
                <span className={layoutStyles.textMuted}>{group.items.length}</span>
              </div>
              <div className={styles['debt-row-list']}>
                {group.items.map((d) => (
                  <DebtRow key={d.id} debt={d} name={counterpartyName(d)} onOpen={() => navigate(`/debts/${d.id}`)} />
                ))}
              </div>
            </div>
          ))}
          {closedDebts.length < closedTotal && (
            <Button variant="secondary" onClick={loadMoreClosed} disabled={loadingClosed}>
              {loadingClosed ? 'Загрузка…' : `Показать ещё (${closedTotal - closedDebts.length})`}
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

function DebtRow({
  debt,
  name,
  onOpen,
  whatsappLink,
  index = 0,
}: {
  debt: Debt
  name: string
  onOpen: () => void
  whatsappLink?: string
  index?: number
}) {
  const Icon = debt.client_id != null ? IconUser : IconTruck
  const overdue = debt.due_date != null && !debt.is_closed && daysOverdue(debt.due_date) > 0

  return (
    <div
      className={[styles['debt-row'], styles['debt-row-in']].join(' ')}
      style={
        {
          '--debt-accent': DEBT_STATUS_ACCENT[debt.status],
          '--row-delay': `${Math.min(index, 12) * 25}ms`,
        } as CSSProperties
      }
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onOpen()
      }}
    >
      <span className={styles['debt-row-icon']}>
        <Icon size={16} stroke={1.8} />
      </span>
      <div className={styles['debt-row-main']}>
        <div className={styles['debt-row-top']}>
          <span className={styles['debt-row-name']}>{name}</span>
          <strong>{formatMoney(debt.balance)} ₽</strong>
          <span className={DEBT_STATUS_BADGE_CLASS[debt.status]}>{DEBT_STATUS_LABELS[debt.status]}</span>
        </div>
        <div className={styles['debt-row-meta']}>
          <span>Остаток из {formatMoney(debt.amount)} ₽</span>
          {debt.due_date && !debt.is_closed && (
            <span className={overdue ? layoutStyles.textDanger : undefined}>
              {overdue
                ? `Просрочен на ${daysOverdue(debt.due_date)} ${pluralDays(daysOverdue(debt.due_date))}`
                : `Срок до ${formatDate(debt.due_date)}`}
            </span>
          )}
          {debt.schedule.length > 0 && (
            <span className={styles['debt-row-installment']}>
              <IconCalendarRepeat size={13} stroke={1.8} /> Рассрочка на {debt.schedule.length}
            </span>
          )}
        </div>
      </div>
      {overdue && whatsappLink && (
        <a
          href={whatsappLink}
          target="_blank"
          rel="noreferrer"
          className={styles['debt-whatsapp']}
          title="Напомнить в WhatsApp"
          onClick={(e) => e.stopPropagation()}
        >
          <IconBrandWhatsapp size={18} stroke={1.8} />
          <span className={styles['debt-whatsapp-label']}>Напомнить</span>
        </a>
      )}
      <IconChevronRight size={18} stroke={1.8} className={styles['debt-row-chevron']} />
    </div>
  )
}
