import { useEffect, useMemo, useState, type CSSProperties, type DragEvent, type FormEvent } from 'react'
import { createPortal } from 'react-dom'
import {
  listActiveTasks,
  listCompletedTasks,
  createTask,
  changeTaskStatus,
  updateTask,
  getTaskHistory,
  type Task,
  type TaskType,
  type TaskStatus,
  type TaskHistoryEntry,
} from '../../entities/task/api'
import { receiveGoods, type Warehouse, type StockItem } from '../../entities/inventory/api'
import type { Product, Unit } from '../../entities/product/api'
import { useCatalog } from '../../app/CatalogContext'
import type { User } from '../../entities/auth/api'
import { useAuth } from '../../app/AuthContext'
import { ApiError } from '../../shared/api/client'
import { formatQuantity, normalizeDecimalInput } from '../../shared/lib/format'
import { Modal } from '../../shared/ui/Modal'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
import { HistoryDisclosure } from '../../shared/ui/HistoryDisclosure'
import kanban from '../../shared/ui/KanbanBoard.module.css'
import { Avatar } from '../../shared/ui/Avatar'
import {
  IconPlus,
  IconClock,
  IconTruck,
  IconChevronRight,
  IconChevronLeft,
  IconLayoutKanban,
  IconTable,
  IconList,
  IconCalendar,
  IconClipboardCheck,
  IconX,
  IconUserQuestion,
  IconUser,
  type Icon as TablerIcon,
} from '@tabler/icons-react'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './TasksPage.module.css'

const STATUS_LABELS: Record<TaskStatus, string> = {
  new: 'Новые',
  in_progress: 'В работе',
  done: 'Готово',
}

const NEXT_STATUS: Record<TaskStatus, TaskStatus | null> = {
  new: 'in_progress',
  in_progress: 'done',
  done: null,
}

const TASK_HISTORY_ACTION_LABELS: Record<string, string> = {
  'task.create': 'Задача создана',
  'task.status': 'Изменён статус',
  'task.update': 'Изменены данные задачи',
}

function formatTaskHistoryDetail(entry: TaskHistoryEntry): string | null {
  const d = entry.details
  if (entry.action === 'task.status' && typeof d.status === 'string') {
    return STATUS_LABELS[d.status as TaskStatus] ?? null
  }
  if (entry.action === 'task.update') {
    const parts: string[] = []
    if ('assigned_user_id' in d) parts.push(d.assigned_user_id == null ? 'исполнитель снят' : 'назначен исполнитель')
    if ('due_date' in d) parts.push(d.due_date == null ? 'срок снят' : `срок ${d.due_date}`)
    if (d.note_changed) parts.push('изменена заметка')
    return parts.length > 0 ? parts.join(', ') : null
  }
  return null
}

const BOARD_STATUSES: TaskStatus[] = ['new', 'in_progress', 'done']
const BOARD_DONE_PAGE_SIZE = 20

const STATUS_ACCENT: Record<TaskStatus, string> = {
  new: 'var(--board-new)',
  in_progress: 'var(--board-progress)',
  done: 'var(--board-ready)',
}

type Tab = 'active' | 'completed'
type ViewMode = 'board' | 'table' | 'list' | 'calendar'

const VIEW_MODE_KEY = 'tasks_view_mode'
const TAB_KEY = 'tasks_tab'

const VIEW_MODE_OPTIONS: { mode: ViewMode; label: string; icon: TablerIcon }[] = [
  { mode: 'board', label: 'Доска', icon: IconLayoutKanban },
  { mode: 'table', label: 'Таблица', icon: IconTable },
  { mode: 'list', label: 'Список', icon: IconList },
  { mode: 'calendar', label: 'Календарь', icon: IconCalendar },
]

function isViewMode(v: string | null): v is ViewMode {
  return v === 'board' || v === 'table' || v === 'list' || v === 'calendar'
}

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const MONTHS = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]

function toISODate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const TASK_TABLE_COLUMNS = '80px 2fr 1fr 1fr 110px 100px 28px'

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDueDate(value: string) {
  return new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function isOverdue(dueDate: string) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return new Date(dueDate) < today
}

export function TasksPage() {
  const { user } = useAuth()
  const canAssignOthers = user?.role === 'owner' || user?.role === 'manager'

  const {
    products,
    warehouses,
    units,
    stock,
    employees,
    ensureProducts,
    ensureWarehouses,
    ensureUnits,
    ensureStock,
    ensureEmployees,
    refresh: refreshCatalog,
  } = useCatalog()
  const [activeTasks, setActiveTasks] = useState<Task[]>([])
  const [completedTasks, setCompletedTasks] = useState<Task[]>([])
  const [boardDoneTasks, setBoardDoneTasks] = useState<Task[]>([])
  const [boardDoneTotal, setBoardDoneTotal] = useState(0)
  const [boardDoneLoadingMore, setBoardDoneLoadingMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [tab, setTab] = useState<Tab>(
    () => (localStorage.getItem(TAB_KEY) === 'completed' ? 'completed' : 'active'),
  )
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    const saved = localStorage.getItem(VIEW_MODE_KEY)
    return isViewMode(saved) ? saved : 'board'
  })
  const [draggedId, setDraggedId] = useState<number | null>(null)
  const [dragOverStatus, setDragOverStatus] = useState<TaskStatus | null>(null)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [doneToast, setDoneToast] = useState<string | null>(null)
  const [completing, setCompleting] = useState<number | null>(null)
  const [moving, setMoving] = useState<Set<number>>(new Set())

  useEffect(() => {
    localStorage.setItem(VIEW_MODE_KEY, viewMode)
  }, [viewMode])

  useEffect(() => {
    localStorage.setItem(TAB_KEY, tab)
  }, [tab])

  useEffect(() => {
    if (!doneToast) return
    const timer = setTimeout(() => setDoneToast(null), 5000)
    return () => clearTimeout(timer)
  }, [doneToast])

  async function load(silent = false) {
    if (!silent) setLoading(true)
    try {
      const [active, completed] = await Promise.all([
        listActiveTasks(),
        listCompletedTasks({ limit: 200 }),
        canAssignOthers ? ensureEmployees() : Promise.resolve<User[]>([]),
        ensureProducts(),
        ensureWarehouses(),
        ensureUnits(),
        ensureStock(),
      ])
      setActiveTasks(active)
      setCompletedTasks(completed.items)
      // BOARD_DONE_PAGE_SIZE (20) заведомо меньше лимита выше (200) — первая
      // страница «доски» это просто срез уже загруженного, без второго запроса
      setBoardDoneTasks(completed.items.slice(0, BOARD_DONE_PAGE_SIZE))
      setBoardDoneTotal(completed.total)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить задачи')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  async function loadMoreBoardDone() {
    if (boardDoneLoadingMore) return
    setBoardDoneLoadingMore(true)
    try {
      const page = await listCompletedTasks({ limit: BOARD_DONE_PAGE_SIZE, offset: boardDoneTasks.length })
      setBoardDoneTasks((prev) => [...prev, ...page.items])
      setBoardDoneTotal(page.total)
    } catch {
      // тихая ошибка — пользователь может повторить нажатие «Показать ещё»
    } finally {
      setBoardDoneLoadingMore(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function moveTo(task: Task, newStatus: TaskStatus) {
    if (task.status === newStatus) return
    if (moving.has(task.id)) return
    setMoving((prev) => new Set(prev).add(task.id))
    try {
      const updated = await changeTaskStatus(task.id, newStatus)
      // "done" — отдельный пагинированный список (total + "показать ещё"),
      // трогать его локально небезопасно (собьётся offset пагинации) —
      // только тут перезагружаем оба списка целиком. Обычное перемещение
      // между активными колонками — просто замена карточки на месте.
      if (task.status === 'done' || newStatus === 'done') {
        load(true)
      } else {
        setActiveTasks((prev) => prev.map((t) => (t.id === task.id ? updated : t)))
      }
    } catch {
      load(true)
    } finally {
      setMoving((prev) => {
        const next = new Set(prev)
        next.delete(task.id)
        return next
      })
    }
  }

  async function complete(task: Task) {
    if (task.type === 'restock' && task.product_id != null && task.warehouse_id != null) {
      if (completing === task.id) return
      setCompleting(task.id)
      try {
        await receiveGoods({
          warehouse_id: task.warehouse_id,
          lines: [{ product_id: task.product_id, quantity: task.quantity ?? '1' }],
        })
        refreshCatalog(['stock']).catch(() => {})
        await changeTaskStatus(task.id, 'done')
        const productName = task.title.replace(/^Дозаказать:\s*/, '')
        setDoneToast(`«${productName}» оформлен на склад — ${formatQuantity(task.quantity ?? '1')} шт`)
        load(true)
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Не удалось оформить приёмку по дозаказу')
      } finally {
        setCompleting(null)
      }
      return
    }
    moveTo(task, 'done')
  }

  function handleAdvance(task: Task) {
    const next = NEXT_STATUS[task.status]
    if (!next) return
    if (next === 'done') {
      complete(task)
    } else {
      moveTo(task, next)
    }
  }

  function handleDragStart(task: Task) {
    setDraggedId(task.id)
  }

  function handleDragEnd() {
    setDraggedId(null)
    setDragOverStatus(null)
  }

  function handleColumnDragOver(e: DragEvent<HTMLDivElement>, status: TaskStatus) {
    e.preventDefault()
    if (dragOverStatus !== status) setDragOverStatus(status)
  }

  function handleColumnDrop(e: DragEvent<HTMLDivElement>, status: TaskStatus) {
    e.preventDefault()
    const task = activeTasks.find((t) => t.id === draggedId)
    setDraggedId(null)
    setDragOverStatus(null)
    if (task) moveTo(task, status)
  }

  const tasks = tab === 'active' ? activeTasks : completedTasks

  return (
    <div className={layoutStyles.stack}>
      <div className={layoutStyles.sectionTitle}>
        <h2>Задачи</h2>
        <Button onClick={() => setShowForm(true)}>
          <IconPlus size={16} stroke={1.8} /> Задача
        </Button>
      </div>

      {showForm && (
        <Modal title="Новая задача" onClose={() => setShowForm(false)}>
          <NewTaskForm
            user={user}
            employees={employees}
            canAssignOthers={canAssignOthers}
            products={products}
            warehouses={warehouses}
            units={units}
            stock={stock}
            onDone={() => {
              setShowForm(false)
              load(true)
            }}
          />
        </Modal>
      )}

      {selectedTask && (
        <Modal title={selectedTask.title} onClose={() => setSelectedTask(null)}>
          <TaskDetail
            task={selectedTask}
            employees={employees}
            canAssignOthers={canAssignOthers}
            onAdvance={(t) => {
              handleAdvance(t)
              setSelectedTask(null)
            }}
            onUpdated={(updated) => {
              setSelectedTask(updated)
              load(true)
            }}
          />
        </Modal>
      )}

      {doneToast && <RestockDoneToast message={doneToast} onClose={() => setDoneToast(null)} />}

      <div className={`${layoutStyles.row} ${layoutStyles.between} ${layoutStyles.wrap}`} style={{ gap: 10 }}>
        <div className={styles.periodTabs}>
          <Button variant="secondary" active={tab === 'active'} onClick={() => setTab('active')}>
            Активные
            {activeTasks.length > 0 && <span className={layoutStyles.countBadge}>{activeTasks.length}</span>}
          </Button>
          <Button variant="secondary" active={tab === 'completed'} onClick={() => setTab('completed')}>
            Завершённые
            {completedTasks.length > 0 && <span className={layoutStyles.countBadge}>{completedTasks.length}</span>}
          </Button>
        </div>
        {tab === 'active' && (
          <div className={styles.viewSwitcher} role="tablist" aria-label="Вид отображения">
            {VIEW_MODE_OPTIONS.map(({ mode, label, icon: Icon }) => (
              <Button
                key={mode}
                variant="secondary"
                active={viewMode === mode}
                onClick={() => setViewMode(mode)}
              >
                <Icon size={15} stroke={1.8} /> {label}
              </Button>
            ))}
          </div>
        )}
      </div>

      {error && <p className={layoutStyles.error}>{error}</p>}
      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : (
      <div key={`${tab}-${viewMode}`} className={styles.viewContent}>
      {tab === 'active' && viewMode === 'table' ? (
        <TasksTableView tasks={activeTasks} onSelect={setSelectedTask} />
      ) : tab === 'active' && viewMode === 'list' ? (
        activeTasks.length === 0 ? (
          <p className={layoutStyles.textMuted}>Активных задач пока нет</p>
        ) : (
          <div className={styles.historyList}>
            {activeTasks.map((t) => (
              <TaskListRow key={t.id} task={t} onSelect={setSelectedTask} onAdvance={handleAdvance} />
            ))}
          </div>
        )
      ) : tab === 'active' && viewMode === 'calendar' ? (
        <TasksCalendarView tasks={activeTasks} onSelect={setSelectedTask} />
      ) : tab === 'active' ? (
        <div className={kanban.board} style={{ '--board-cols': BOARD_STATUSES.length } as CSSProperties}>
          {BOARD_STATUSES.map((status) => {
            const columnTasks = status === 'done' ? boardDoneTasks : activeTasks.filter((t) => t.status === status)
            const columnCount = status === 'done' ? boardDoneTotal : columnTasks.length
            return (
              <div
                key={status}
                className={`${kanban.column}${dragOverStatus === status ? ` ${kanban.columnOver}` : ''}`}
                style={{ '--col-accent': STATUS_ACCENT[status] } as CSSProperties}
                onDragOver={(e) => handleColumnDragOver(e, status)}
                onDragLeave={() => setDragOverStatus((s) => (s === status ? null : s))}
                onDrop={(e) => handleColumnDrop(e, status)}
              >
                <div className={kanban.columnHead}>
                  <span className={kanban.dot} />
                  <span>{STATUS_LABELS[status]}</span>
                  <span className={kanban.columnCount}>{columnCount}</span>
                </div>
                <div className={kanban.columnBody}>
                  {columnTasks.length === 0 ? (
                    status === 'new' ? (
                      <button
                        type="button"
                        className={`${kanban.empty} ${kanban.emptyAction}`}
                        onClick={() => setShowForm(true)}
                      >
                        <IconPlus size={16} stroke={1.8} /> Создать задачу
                      </button>
                    ) : (
                      <div className={kanban.empty}>Пусто</div>
                    )
                  ) : (
                    columnTasks.map((t) => {
                      const overdue = t.due_date != null && isOverdue(t.due_date)
                      const draggableCard = status !== 'done'
                      return (
                        <div
                          key={t.id}
                          className={`${kanban.card}${draggedId === t.id ? ` ${kanban.cardDragging}` : ''}`}
                          draggable={draggableCard}
                          onDragStart={draggableCard ? () => handleDragStart(t) : undefined}
                          onDragEnd={draggableCard ? handleDragEnd : undefined}
                          onClick={() => setSelectedTask(t)}
                        >
                          <span className={kanban.cardAccent} />
                          <div className={kanban.cardHead}>
                            <span className={kanban.cardNumber}>
                              №{t.number ?? t.id}
                            </span>
                            {t.type === 'restock' && (
                              <span className="badge accent">
                                <IconTruck size={12} stroke={1.8} /> Дозаказ ×{formatQuantity(t.quantity ?? '1')}
                              </span>
                            )}
                          </div>
                          <strong className={kanban.cardTitle}>{t.title}</strong>
                          <div className={kanban.cardFooter}>
                            {t.due_date ? (
                              <span
                                className={`${kanban.cardDue}${overdue ? ` ${kanban.cardDueOverdue}` : ''}`}
                              >
                                <IconClock size={13} stroke={1.8} /> {formatDueDate(t.due_date)}
                              </span>
                            ) : (
                              <span />
                            )}
                            <div className={styles.boardCardPeople}>
                              {t.created_by_name && (
                                <Avatar name={t.created_by_name} variant="muted" title={`Создал: ${t.created_by_name}`} />
                              )}
                              <Avatar
                                name={t.assigned_user_name}
                                icon={<IconUserQuestion size={13} stroke={1.8} />}
                                title={t.assigned_user_name ? `Назначено: ${t.assigned_user_name}` : 'Не назначено'}
                              />
                            </div>
                          </div>
                        </div>
                      )
                    })
                  )}
                  {status === 'done' && boardDoneTasks.length < boardDoneTotal && (
                    <button
                      type="button"
                      className={kanban.loadMore}
                      onClick={loadMoreBoardDone}
                      disabled={boardDoneLoadingMore}
                    >
                      {boardDoneLoadingMore ? 'Загрузка…' : `Показать ещё (${boardDoneTotal - boardDoneTasks.length})`}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ) : tasks.length === 0 ? (
        <p className={layoutStyles.textMuted}>Завершённых задач пока нет</p>
      ) : (
        <div className={styles.historyList}>
          {tasks.map((t) => (
            <div key={t.id} className={`${layoutStyles.card} ${styles.historyCard}`} onClick={() => setSelectedTask(t)}>
              <div className={styles.historyCardMain}>
                <div className={styles.historyCardTitle}>
                  <strong>№{t.number ?? t.id}</strong>
                  <span>{t.title}</span>
                </div>
                {t.completed_at && (
                  <span className={layoutStyles.textMuted}>Выполнена {formatDateTime(t.completed_at)}</span>
                )}
              </div>
              <div className={styles.boardCardPeople}>
                {t.created_by_name && (
                  <Avatar name={t.created_by_name} variant="muted" title={`Создал: ${t.created_by_name}`} />
                )}
                <Avatar
                  name={t.assigned_user_name}
                  icon={<IconUserQuestion size={13} stroke={1.8} />}
                  title={t.assigned_user_name ? `Назначено: ${t.assigned_user_name}` : 'Не назначено'}
                />
              </div>
            </div>
          ))}
        </div>
      )}
      </div>
      )}
    </div>
  )
}

function RestockDoneToast({ message, onClose }: { message: string; onClose: () => void }) {
  return createPortal(
    <div className={styles.restockToast} role="status">
      <span className={styles.restockToastIcon}>
        <IconClipboardCheck size={20} stroke={1.8} />
      </span>
      <div className={styles.restockToastBody}>
        <span className={styles.restockToastTitle}>{message}</span>
      </div>
      <button type="button" className={styles.restockToastClose} onClick={onClose} aria-label="Закрыть">
        <IconX size={14} stroke={1.8} />
      </button>
    </div>,
    document.body,
  )
}

function TasksTableView({ tasks, onSelect }: { tasks: Task[]; onSelect: (task: Task) => void }) {
  if (tasks.length === 0) return <p className={layoutStyles.textMuted}>Активных задач пока нет</p>
  return (
    <div className={layoutStyles.dataTable}>
      <div className={layoutStyles.dataTableHead} style={{ gridTemplateColumns: TASK_TABLE_COLUMNS }}>
        <span>№</span>
        <span>Название</span>
        <span>Исполнитель</span>
        <span>Создал</span>
        <span>Статус</span>
        <span>Срок</span>
        <span />
      </div>
      <div className={layoutStyles.dataTableBody}>
        {tasks.map((t, i) => {
          const overdue = t.due_date != null && isOverdue(t.due_date)
          return (
            <button
              key={t.id}
              type="button"
              className={`${layoutStyles.dataRow} ${layoutStyles.dataRowLink} ${styles.rowIn}`}
              style={
                {
                  gridTemplateColumns: TASK_TABLE_COLUMNS,
                  '--row-delay': `${Math.min(i, 12) * 25}ms`,
                } as CSSProperties
              }
              onClick={() => onSelect(t)}
            >
              <span className={layoutStyles.dataRowName}>№{t.number ?? t.id}</span>
              <span>
                {t.title}
                {t.type === 'restock' && (
                  <span className="badge accent" style={{ marginLeft: 6 }}>
                    <IconTruck size={12} stroke={1.8} /> Дозаказ ×{formatQuantity(t.quantity ?? '1')}
                  </span>
                )}
              </span>
              <span className={layoutStyles.textMuted}>{t.assigned_user_name ?? '—'}</span>
              <span className={layoutStyles.textMuted}>{t.created_by_name ?? '—'}</span>
              <span className="badge">{STATUS_LABELS[t.status]}</span>
              <span className={overdue ? styles.boardCardDueOverdue : layoutStyles.textMuted}>
                {t.due_date ? formatDueDate(t.due_date) : '—'}
              </span>
              <IconChevronRight size={16} stroke={1.8} className={layoutStyles.dataRowChevron} />
            </button>
          )
        })}
      </div>
    </div>
  )
}

function TaskListRow({
  task,
  onSelect,
  onAdvance,
}: {
  task: Task
  onSelect: (task: Task) => void
  onAdvance: (task: Task) => void
}) {
  const next = NEXT_STATUS[task.status]
  const overdue = task.due_date != null && isOverdue(task.due_date)
  return (
    <div className={`${layoutStyles.card} ${styles.historyCard}`} onClick={() => onSelect(task)}>
      <div className={styles.historyCardMain}>
        <div className={styles.historyCardTitle}>
          <strong>№{task.number ?? task.id}</strong>
          <span>{task.title}</span>
          {task.type === 'restock' && (
            <span className="badge accent">
              <IconTruck size={12} stroke={1.8} /> Дозаказ ×{formatQuantity(task.quantity ?? '1')}
            </span>
          )}
        </div>
        {task.due_date && (
          <span className={overdue ? styles.boardCardDueOverdue : layoutStyles.textMuted}>
            <IconClock size={13} stroke={1.8} /> до {formatDueDate(task.due_date)}
          </span>
        )}
      </div>
      <div className={layoutStyles.row} style={{ gap: 10 }}>
        <div className={styles.boardCardPeople}>
          {task.created_by_name && (
            <Avatar name={task.created_by_name} variant="muted" title={`Создал: ${task.created_by_name}`} />
          )}
          <Avatar
            name={task.assigned_user_name}
            icon={<IconUserQuestion size={13} stroke={1.8} />}
            title={task.assigned_user_name ? `Назначено: ${task.assigned_user_name}` : 'Не назначено'}
          />
        </div>
        {next && (
          <Button
            variant={next === 'done' ? 'primary' : 'secondary'}
            onClick={(e) => {
              e.stopPropagation()
              onAdvance(task)
            }}
          >
            {next === 'done' && task.type === 'restock' ? 'Принять на склад' : `→ ${STATUS_LABELS[next]}`}
          </Button>
        )}
      </div>
    </div>
  )
}

function TasksCalendarView({ tasks, onSelect }: { tasks: Task[]; onSelect: (task: Task) => void }) {
  const [cursor, setCursor] = useState(() => new Date())
  const year = cursor.getFullYear()
  const month = cursor.getMonth()

  const byDay = useMemo(() => {
    const map = new Map<string, Task[]>()
    for (const t of tasks) {
      if (!t.due_date) continue
      const list = map.get(t.due_date) ?? []
      list.push(t)
      map.set(t.due_date, list)
    }
    return map
  }, [tasks])

  const unscheduled = useMemo(() => tasks.filter((t) => !t.due_date), [tasks])

  const cells = useMemo(() => {
    const first = new Date(year, month, 1)
    const startOffset = (first.getDay() + 6) % 7
    const start = new Date(year, month, 1 - startOffset)
    return Array.from(
      { length: 42 },
      (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i),
    )
  }, [year, month])

  const todayISO = toISODate(new Date())

  return (
    <div className={styles.viewCalendar}>
      <div className={styles.viewCalendarHeader}>
        <div className={styles.viewCalendarNav}>
          <IconButton
            variant="muted"
            onClick={() => setCursor(new Date(year, month - 1, 1))}
            aria-label="Предыдущий месяц"
          >
            <IconChevronLeft size={16} stroke={1.8} />
          </IconButton>
          <IconButton
            variant="muted"
            onClick={() => setCursor(new Date(year, month + 1, 1))}
            aria-label="Следующий месяц"
          >
            <IconChevronRight size={16} stroke={1.8} />
          </IconButton>
        </div>
        <span className={styles.viewCalendarTitle}>
          {MONTHS[month]} {year}
        </span>
        <Button variant="secondary" onClick={() => setCursor(new Date())}>
          Сегодня
        </Button>
      </div>
      <div className={styles.viewCalendarWeekdays}>
        {WEEKDAYS.map((w) => (
          <span key={w}>{w}</span>
        ))}
      </div>
      <div className={styles.viewCalendarGrid}>
        {cells.map((date, i) => {
          const iso = toISODate(date)
          const inMonth = date.getMonth() === month
          const dayTasks = byDay.get(iso) ?? []
          const visible = dayTasks.slice(0, 3)
          const overflow = dayTasks.length - visible.length
          return (
            <div key={i} className={`${styles.viewCalendarCell}${inMonth ? '' : ` ${styles.viewCalendarCellOutside}`}`}>
              <span className={`${styles.viewCalendarDate}${iso === todayISO ? ` ${styles.viewCalendarDateToday}` : ''}`}>
                {date.getDate()}
              </span>
              {visible.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={styles.viewCalendarEntry}
                  onClick={() => onSelect(t)}
                  title={`№${t.number ?? t.id} · ${t.title}`}
                >
                  {t.title}
                </button>
              ))}
              {overflow > 0 && (
                <span className={`${styles.viewCalendarEntry} ${styles.viewCalendarEntryMore}`}>+{overflow}</span>
              )}
            </div>
          )
        })}
      </div>
      {unscheduled.length > 0 && (
        <div className={styles.viewCalendarUnscheduled}>
          <span className={styles.viewCalendarUnscheduledTitle}>Без срока · {unscheduled.length}</span>
          <div className={styles.historyList}>
            {unscheduled.map((t) => (
              <div key={t.id} className={`${layoutStyles.card} ${styles.historyCard}`} onClick={() => onSelect(t)}>
                <div className={styles.historyCardMain}>
                  <div className={styles.historyCardTitle}>
                    <strong>№{t.number ?? t.id}</strong>
                    <span>{t.title}</span>
                  </div>
                </div>
                <div className={styles.boardCardPeople}>
                  {t.created_by_name && (
                    <Avatar name={t.created_by_name} variant="muted" title={`Создал: ${t.created_by_name}`} />
                  )}
                  <Avatar
                    name={t.assigned_user_name}
                    icon={<IconUserQuestion size={13} stroke={1.8} />}
                    title={t.assigned_user_name ? `Назначено: ${t.assigned_user_name}` : 'Не назначено'}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function TaskDetail({
  task,
  employees,
  canAssignOthers,
  onAdvance,
  onUpdated,
}: {
  task: Task
  employees: User[]
  canAssignOthers: boolean
  onAdvance?: (task: Task) => void
  onUpdated: (task: Task) => void
}) {
  const next = NEXT_STATUS[task.status]
  const [saving, setSaving] = useState(false)
  const [noteDraft, setNoteDraft] = useState(task.note)
  const [noteFocused, setNoteFocused] = useState(false)

  const canEditAssignee = canAssignOthers || task.assigned_user_id == null
  const assigneeOptions = [
    { value: '', label: 'Не назначен' },
    ...employees.map((e) => ({ value: String(e.id), label: e.name })),
  ]

  // Пока заметка не в фокусе, черновик всегда синхронизирован с задачей —
  // без этого после сохранения другого поля (onUpdated меняет task) заметка
  // могла бы показать устаревший черновик.
  if (!noteFocused && noteDraft !== task.note) setNoteDraft(task.note)

  async function save(patch: Parameters<typeof updateTask>[1]) {
    setSaving(true)
    try {
      const updated = await updateTask(task.id, patch)
      onUpdated(updated)
    } finally {
      setSaving(false)
    }
  }

  function saveNoteIfChanged() {
    setNoteFocused(false)
    if (noteDraft !== task.note) save({ note: noteDraft })
  }

  return (
    <div className={layoutStyles.stack}>
      <div className={`${layoutStyles.row} ${layoutStyles.between} ${layoutStyles.wrap}`} style={{ gap: 8 }}>
        <div className={`${layoutStyles.row} ${layoutStyles.wrap}`} style={{ gap: 6 }}>
          <span className="badge accent">{STATUS_LABELS[task.status]}</span>
          {task.type === 'restock' && (
            <span className="badge">
              <IconTruck size={12} stroke={1.8} /> Дозаказ
            </span>
          )}
        </div>
        {next && onAdvance && (
          <Button variant={next === 'done' ? 'primary' : 'secondary'} onClick={() => onAdvance(task)}>
            {next === 'done' && task.type === 'restock' ? 'Принять на склад' : `→ ${STATUS_LABELS[next]}`}
          </Button>
        )}
      </div>
      {task.type === 'restock' && task.quantity != null && (
        <div className={layoutStyles.stack} style={{ gap: 2 }}>
          <span className={layoutStyles.fieldLabel}>Количество для дозаказа</span>
          <strong>{formatQuantity(task.quantity)}</strong>
        </div>
      )}
      <div className={styles.metaGrid}>
        <div className={styles.personCard}>
          <Avatar name={task.assigned_user_name} size="md" icon={<IconUserQuestion size={16} stroke={1.8} />} />
          <span className={styles.personCardBody}>
            <span className={layoutStyles.fieldLabel}>Исполнитель</span>
            <Select
              className={styles.inlineEditSelect}
              value={task.assigned_user_id != null ? String(task.assigned_user_id) : ''}
              onChange={(v) => save({ assigned_user_id: v ? Number(v) : null })}
              options={assigneeOptions}
              disabled={!canEditAssignee || saving}
            />
            {task.created_by_name && (
              <span className={styles.createdByHint}>Создал: {task.created_by_name}</span>
            )}
          </span>
        </div>
        <div className={layoutStyles.stack} style={{ gap: 2 }}>
          <span className={layoutStyles.fieldLabel}>Срок</span>
          <DateInput
            className={styles.inlineEditDate}
            value={task.due_date ?? ''}
            onChange={(v) => save({ due_date: v || null })}
            disabled={saving}
          />
          {task.due_date && (
            <button
              type="button"
              className={styles.inlineClearBtn}
              onClick={() => save({ due_date: null })}
              disabled={saving}
            >
              Снять срок
            </button>
          )}
        </div>
      </div>
      <div className={layoutStyles.stack} style={{ gap: 2 }}>
        <span className={layoutStyles.fieldLabel}>Заметка</span>
        <textarea
          className={styles.inlineEditTextarea}
          value={noteDraft}
          onChange={(e) => setNoteDraft(e.target.value)}
          onFocus={() => setNoteFocused(true)}
          onBlur={saveNoteIfChanged}
          placeholder="Добавить заметку"
          disabled={saving}
          rows={2}
        />
      </div>
      <HistoryDisclosure
        load={() => getTaskHistory(task.id)}
        actionLabels={TASK_HISTORY_ACTION_LABELS}
        formatDetail={formatTaskHistoryDetail}
        emptyMessage="Записей нет"
      />
    </div>
  )
}

const TASK_TYPE_OPTIONS: { value: TaskType; label: string }[] = [
  { value: 'general', label: 'Обычная' },
  { value: 'restock', label: 'Дозаказ' },
]

function NewTaskForm({
  user,
  employees,
  canAssignOthers,
  products,
  warehouses,
  units,
  stock,
  onDone,
}: {
  user: User | null
  employees: User[]
  canAssignOthers: boolean
  products: Product[]
  warehouses: Warehouse[]
  units: Unit[]
  stock: StockItem[]
  onDone: () => void
}) {
  const [type, setType] = useState<TaskType>('general')
  const [title, setTitle] = useState('')
  const [note, setNote] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [assignedUserId, setAssignedUserId] = useState<number | null>(user?.id ?? null)
  const [productId, setProductId] = useState<number | null>(null)
  const [warehouseId, setWarehouseId] = useState<number | null>(warehouses[0]?.id ?? null)
  const [quantity, setQuantity] = useState('1')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const assigneeOptions = user
    ? [
        { value: String(user.id), label: 'Себе' },
        ...employees.filter((e) => e.id !== user.id).map((e) => ({ value: String(e.id), label: e.name })),
      ]
    : []

  const productOptions = products.map((p) => ({ value: String(p.id), label: p.name }))
  const warehouseOptions = warehouses.map((w) => ({ value: String(w.id), label: w.name }))

  const selectedProduct = productId != null ? products.find((p) => p.id === productId) ?? null : null
  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code
  const isFractional = selectedProduct ? units.find((u) => u.code === selectedProduct.unit_code)?.fractional ?? false : false
  const availableQty =
    productId != null && warehouseId != null
      ? stock
          .filter((s) => s.product_id === productId && s.warehouse_id === warehouseId)
          .reduce((sum, s) => sum + Number(s.quantity), 0)
      : null

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (type === 'restock') {
      if (productId == null || warehouseId == null || !quantity.trim()) return
    } else if (!title.trim()) {
      return
    }
    setError(null)
    setSaving(true)
    try {
      if (type === 'restock' && selectedProduct) {
        await createTask({
          title: `Дозаказать: ${selectedProduct.name}`,
          type: 'restock',
          product_id: productId,
          warehouse_id: warehouseId,
          quantity,
          assigned_user_id: assignedUserId,
          note,
          due_date: dueDate || null,
        })
      } else {
        await createTask({
          title: title.trim(),
          assigned_user_id: assignedUserId,
          note,
          due_date: dueDate || null,
        })
      }
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать задачу')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className={layoutStyles.form} onSubmit={handleSubmit}>
      {type === 'restock' ? (
        <>
          <label className={layoutStyles.field}>
            Товар
            <Select
              value={productId != null ? String(productId) : ''}
              onChange={(v) => setProductId(Number(v))}
              options={productOptions}
              placeholder="Выберите товар"
            />
          </label>
          <label className={layoutStyles.field}>
            Склад
            <Select
              value={warehouseId != null ? String(warehouseId) : ''}
              onChange={(v) => setWarehouseId(Number(v))}
              options={warehouseOptions}
              placeholder="Выберите склад"
            />
          </label>
          <label className={layoutStyles.field}>
            Количество
            <div className={layoutStyles.row} style={{ gap: 8, alignItems: 'center' }}>
              <input
                type="text"
                inputMode="decimal"
                value={quantity}
                onChange={(e) => {
                  const normalized = normalizeDecimalInput(e.target.value)
                  if (normalized === null) return
                  const value = !isFractional && normalized.includes('.') ? normalized.split('.')[0] || '0' : normalized
                  setQuantity(value)
                }}
                style={{ maxWidth: 100 }}
              />
              {selectedProduct && <span className={layoutStyles.textMuted}>{unitName(selectedProduct.unit_code)}</span>}
            </div>
            {availableQty !== null && (
              <span className={layoutStyles.textMuted} style={{ fontSize: 12 }}>
                Остаток на складе: {formatQuantity(String(availableQty))}{' '}
                {selectedProduct ? unitName(selectedProduct.unit_code) : ''}
              </span>
            )}
          </label>
        </>
      ) : (
        <label className={layoutStyles.field}>
          Название
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Позвонить поставщику" autoFocus />
        </label>
      )}
      <label className={layoutStyles.field}>
        Заметка
        <textarea
          className={styles.taskFormNote}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="детали…"
          rows={5}
        />
      </label>
      <div className={styles.taskFormMetaRow}>
        <label className={layoutStyles.field}>
          Тип задачи
          <div className={styles.taskFormIconField}>
            <IconClipboardCheck size={16} stroke={1.8} className={styles.taskFormIconFieldIcon} />
            <Select
              className={styles.taskFormIconFieldControl}
              value={type}
              onChange={(v) => setType(v as TaskType)}
              options={TASK_TYPE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
            />
          </div>
        </label>
        {canAssignOthers && (
          <label className={layoutStyles.field}>
            Исполнитель
            <div className={styles.taskFormIconField}>
              <IconUser size={16} stroke={1.8} className={styles.taskFormIconFieldIcon} />
              <Select
                className={styles.taskFormIconFieldControl}
                value={assignedUserId != null ? String(assignedUserId) : ''}
                onChange={(v) => setAssignedUserId(Number(v))}
                options={assigneeOptions}
              />
            </div>
          </label>
        )}
        <label className={layoutStyles.field}>
          Срок
          <DateInput value={dueDate} onChange={setDueDate} />
        </label>
      </div>
      {error && <p className={layoutStyles.error}>{error}</p>}
      <Button
        type="submit"
        disabled={saving || (type === 'restock' ? productId == null || warehouseId == null || !quantity.trim() : !title.trim())}
      >
        {saving ? 'Сохранение…' : 'Создать задачу'}
      </Button>
    </form>
  )
}
