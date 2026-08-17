import { useEffect, useMemo, useState, type CSSProperties, type DragEvent, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  listActiveTasks,
  listCompletedTasks,
  createTask,
  changeTaskStatus,
  getTaskHistory,
  type Task,
  type TaskStatus,
  type TaskHistoryEntry,
} from '../../entities/task/api'
import { listEmployees } from '../../entities/profile/api'
import type { User } from '../../entities/auth/api'
import { useAuth } from '../../app/AuthContext'
import { saveReceiveDraft } from '../stock/receiveDraft'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { Select } from '../../shared/ui/Select'
import { DateInput } from '../../shared/ui/DateInput'
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
  type Icon as TablerIcon,
} from '@tabler/icons-react'

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

const BOARD_STATUSES: TaskStatus[] = ['new', 'in_progress']

const STATUS_ACCENT: Record<TaskStatus, string> = {
  new: 'var(--board-new)',
  in_progress: 'var(--board-progress)',
  done: 'var(--board-ready)',
}

type Tab = 'active' | 'completed'
type ViewMode = 'board' | 'table' | 'list' | 'calendar'

const VIEW_MODE_KEY = 'tasks_view_mode'

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

const TASK_TABLE_COLUMNS = '80px 2fr 1fr 110px 100px 28px'

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

function initials(name: string) {
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase()
}

export function TasksPage() {
  const { user } = useAuth()
  const canAssignOthers = user?.role === 'owner' || user?.role === 'manager'

  const [activeTasks, setActiveTasks] = useState<Task[]>([])
  const [completedTasks, setCompletedTasks] = useState<Task[]>([])
  const [employees, setEmployees] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [tab, setTab] = useState<Tab>('active')
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    const saved = localStorage.getItem(VIEW_MODE_KEY)
    return isViewMode(saved) ? saved : 'board'
  })
  const [draggedId, setDraggedId] = useState<number | null>(null)
  const [dragOverStatus, setDragOverStatus] = useState<TaskStatus | null>(null)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)

  const navigate = useNavigate()

  useEffect(() => {
    localStorage.setItem(VIEW_MODE_KEY, viewMode)
  }, [viewMode])

  async function load(silent = false) {
    if (!silent) setLoading(true)
    try {
      const [active, completed, emp] = await Promise.all([
        listActiveTasks(),
        listCompletedTasks(),
        canAssignOthers ? listEmployees() : Promise.resolve<User[]>([]),
      ])
      setActiveTasks(active)
      setCompletedTasks(completed)
      setEmployees(emp)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить задачи')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function moveTo(task: Task, newStatus: TaskStatus) {
    if (task.status === newStatus) return
    try {
      await changeTaskStatus(task.id, newStatus)
      load(true)
    } catch {
      load(true)
    }
  }

  function complete(task: Task) {
    if (task.type === 'restock' && task.product_id != null && task.warehouse_id != null) {
      saveReceiveDraft({
        warehouseId: task.warehouse_id,
        lines: [{ productId: task.product_id, quantity: task.quantity ?? '1' }],
        fromTaskId: task.id,
      })
      navigate(`/stock/${task.warehouse_id}?open=receive`)
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
    <div className="stack">
      <div className="section-title">
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
            onAdvance={(t) => {
              handleAdvance(t)
              setSelectedTask(null)
            }}
          />
        </Modal>
      )}

      <div className="row between wrap" style={{ gap: 10 }}>
        <div className="sale-period-tabs">
          <Button variant="secondary" active={tab === 'active'} onClick={() => setTab('active')}>
            Активные
            {activeTasks.length > 0 && <span className="count-badge">{activeTasks.length}</span>}
          </Button>
          <Button variant="secondary" active={tab === 'completed'} onClick={() => setTab('completed')}>
            Завершённые
            {completedTasks.length > 0 && <span className="count-badge">{completedTasks.length}</span>}
          </Button>
        </div>
        {tab === 'active' && (
          <div className="view-switcher" role="tablist" aria-label="Вид отображения">
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

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : tab === 'active' && viewMode === 'table' ? (
        <TasksTableView tasks={activeTasks} onSelect={setSelectedTask} />
      ) : tab === 'active' && viewMode === 'list' ? (
        activeTasks.length === 0 ? (
          <p className="text-muted">Активных задач пока нет</p>
        ) : (
          <div className="orders-history-list">
            {activeTasks.map((t) => (
              <TaskListRow key={t.id} task={t} onSelect={setSelectedTask} onAdvance={handleAdvance} />
            ))}
          </div>
        )
      ) : tab === 'active' && viewMode === 'calendar' ? (
        <TasksCalendarView tasks={activeTasks} onSelect={setSelectedTask} />
      ) : tab === 'active' ? (
        <div className="orders-board" style={{ '--board-cols': BOARD_STATUSES.length } as CSSProperties}>
          {BOARD_STATUSES.map((status) => {
            const columnTasks = activeTasks.filter((t) => t.status === status)
            return (
              <div
                key={status}
                className={`orders-board-column${dragOverStatus === status ? ' orders-board-column-over' : ''}`}
                style={{ '--col-accent': STATUS_ACCENT[status] } as CSSProperties}
                onDragOver={(e) => handleColumnDragOver(e, status)}
                onDragLeave={() => setDragOverStatus((s) => (s === status ? null : s))}
                onDrop={(e) => handleColumnDrop(e, status)}
              >
                <div className="orders-board-column-head">
                  <span>{STATUS_LABELS[status]}</span>
                  <span className="orders-board-column-count">{columnTasks.length}</span>
                </div>
                <div className="orders-board-column-body">
                  {columnTasks.length === 0 ? (
                    status === 'new' ? (
                      <button
                        type="button"
                        className="orders-board-empty orders-board-empty-action"
                        onClick={() => setShowForm(true)}
                      >
                        <IconPlus size={16} stroke={1.8} /> Создать задачу
                      </button>
                    ) : (
                      <div className="orders-board-empty">Пусто</div>
                    )
                  ) : (
                    columnTasks.map((t) => {
                      const overdue = t.due_date != null && isOverdue(t.due_date)
                      return (
                        <div
                          key={t.id}
                          className={`orders-board-card${draggedId === t.id ? ' orders-board-card-dragging' : ''}`}
                          draggable
                          onDragStart={() => handleDragStart(t)}
                          onDragEnd={handleDragEnd}
                          onClick={() => setSelectedTask(t)}
                        >
                          <div className="orders-board-card-head">
                            <span className="orders-board-card-number">№{t.number ?? t.id}</span>
                            {t.type === 'restock' && (
                              <span className="badge accent">
                                <IconTruck size={12} stroke={1.8} /> Дозаказ
                              </span>
                            )}
                          </div>
                          <strong className="orders-board-card-client">{t.title}</strong>
                          <div className="orders-board-card-footer">
                            {t.due_date ? (
                              <span
                                className={`orders-board-card-due${overdue ? ' orders-board-card-due-overdue' : ''}`}
                              >
                                <IconClock size={13} stroke={1.8} /> {formatDueDate(t.due_date)}
                              </span>
                            ) : (
                              <span />
                            )}
                            {t.assigned_user_name && (
                              <span className="orders-board-card-avatar" title={t.assigned_user_name}>
                                {initials(t.assigned_user_name)}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ) : tasks.length === 0 ? (
        <p className="text-muted">Завершённых задач пока нет</p>
      ) : (
        <div className="orders-history-list">
          {tasks.map((t) => (
            <div key={t.id} className="card orders-history-card" onClick={() => setSelectedTask(t)}>
              <div className="orders-history-card-main">
                <div className="orders-history-card-title">
                  <strong>№{t.number ?? t.id}</strong>
                  <span>{t.title}</span>
                </div>
                {t.completed_at && (
                  <span className="text-muted">Выполнена {formatDateTime(t.completed_at)}</span>
                )}
              </div>
              {t.assigned_user_name && (
                <span className="orders-board-card-avatar" title={t.assigned_user_name}>
                  {initials(t.assigned_user_name)}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function TasksTableView({ tasks, onSelect }: { tasks: Task[]; onSelect: (task: Task) => void }) {
  if (tasks.length === 0) return <p className="text-muted">Активных задач пока нет</p>
  return (
    <div className="data-table">
      <div className="data-table-head" style={{ gridTemplateColumns: TASK_TABLE_COLUMNS }}>
        <span>№</span>
        <span>Название</span>
        <span>Исполнитель</span>
        <span>Статус</span>
        <span>Срок</span>
        <span />
      </div>
      <div className="data-table-body">
        {tasks.map((t, i) => {
          const overdue = t.due_date != null && isOverdue(t.due_date)
          return (
            <button
              key={t.id}
              type="button"
              className="data-row data-row-link sale-history-row-in"
              style={
                {
                  gridTemplateColumns: TASK_TABLE_COLUMNS,
                  '--row-delay': `${Math.min(i, 12) * 25}ms`,
                } as CSSProperties
              }
              onClick={() => onSelect(t)}
            >
              <span className="data-row-name">№{t.number ?? t.id}</span>
              <span>
                {t.title}
                {t.type === 'restock' && (
                  <span className="badge accent" style={{ marginLeft: 6 }}>
                    <IconTruck size={12} stroke={1.8} /> Дозаказ
                  </span>
                )}
              </span>
              <span className="text-muted">{t.assigned_user_name ?? '—'}</span>
              <span className="badge">{STATUS_LABELS[t.status]}</span>
              <span className={overdue ? 'orders-board-card-due-overdue' : 'text-muted'}>
                {t.due_date ? formatDueDate(t.due_date) : '—'}
              </span>
              <IconChevronRight size={16} stroke={1.8} className="data-row-chevron" />
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
    <div className="card orders-history-card" onClick={() => onSelect(task)}>
      <div className="orders-history-card-main">
        <div className="orders-history-card-title">
          <strong>№{task.number ?? task.id}</strong>
          <span>{task.title}</span>
          {task.type === 'restock' && (
            <span className="badge accent">
              <IconTruck size={12} stroke={1.8} /> Дозаказ
            </span>
          )}
        </div>
        {task.due_date && (
          <span className={overdue ? 'orders-board-card-due-overdue' : 'text-muted'}>
            <IconClock size={13} stroke={1.8} /> до {formatDueDate(task.due_date)}
          </span>
        )}
      </div>
      <div className="row" style={{ gap: 10 }}>
        {task.assigned_user_name && (
          <span className="orders-board-card-avatar" title={task.assigned_user_name}>
            {initials(task.assigned_user_name)}
          </span>
        )}
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
    <div className="view-calendar">
      <div className="view-calendar-header">
        <div className="view-calendar-nav">
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
        <span className="view-calendar-title">
          {MONTHS[month]} {year}
        </span>
        <Button variant="secondary" onClick={() => setCursor(new Date())}>
          Сегодня
        </Button>
      </div>
      <div className="view-calendar-weekdays">
        {WEEKDAYS.map((w) => (
          <span key={w}>{w}</span>
        ))}
      </div>
      <div className="view-calendar-grid">
        {cells.map((date, i) => {
          const iso = toISODate(date)
          const inMonth = date.getMonth() === month
          const dayTasks = byDay.get(iso) ?? []
          const visible = dayTasks.slice(0, 3)
          const overflow = dayTasks.length - visible.length
          return (
            <div key={i} className={`view-calendar-cell${inMonth ? '' : ' view-calendar-cell-outside'}`}>
              <span className={`view-calendar-date${iso === todayISO ? ' view-calendar-date-today' : ''}`}>
                {date.getDate()}
              </span>
              {visible.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className="view-calendar-entry"
                  onClick={() => onSelect(t)}
                  title={`№${t.number ?? t.id} · ${t.title}`}
                >
                  {t.title}
                </button>
              ))}
              {overflow > 0 && <span className="view-calendar-entry view-calendar-entry-more">+{overflow}</span>}
            </div>
          )
        })}
      </div>
      {unscheduled.length > 0 && (
        <div className="view-calendar-unscheduled">
          <span className="view-calendar-unscheduled-title">Без срока · {unscheduled.length}</span>
          <div className="orders-history-list">
            {unscheduled.map((t) => (
              <div key={t.id} className="card orders-history-card" onClick={() => onSelect(t)}>
                <div className="orders-history-card-main">
                  <div className="orders-history-card-title">
                    <strong>№{t.number ?? t.id}</strong>
                    <span>{t.title}</span>
                  </div>
                </div>
                {t.assigned_user_name && (
                  <span className="orders-board-card-avatar" title={t.assigned_user_name}>
                    {initials(t.assigned_user_name)}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function TaskDetail({ task, onAdvance }: { task: Task; onAdvance?: (task: Task) => void }) {
  const [history, setHistory] = useState<TaskHistoryEntry[] | null>(null)
  const [open, setOpen] = useState(false)
  const next = NEXT_STATUS[task.status]

  async function toggleHistory() {
    if (!open && history === null) {
      try {
        setHistory(await getTaskHistory(task.id))
      } catch {
        setHistory([])
      }
    }
    setOpen((v) => !v)
  }

  return (
    <div className="stack">
      <div className="row between wrap" style={{ gap: 8 }}>
        <div className="row wrap" style={{ gap: 6 }}>
          <span className="badge accent">{STATUS_LABELS[task.status]}</span>
          {task.type === 'restock' && <span className="badge">Дозаказ</span>}
          {task.due_date && <span className="badge">до {task.due_date}</span>}
        </div>
        {next && onAdvance && (
          <Button variant={next === 'done' ? 'primary' : 'secondary'} onClick={() => onAdvance(task)}>
            {next === 'done' && task.type === 'restock' ? 'Принять на склад' : `→ ${STATUS_LABELS[next]}`}
          </Button>
        )}
      </div>
      {task.assigned_user_name && (
        <div className="stack" style={{ gap: 2 }}>
          <span className="field-label">Исполнитель</span>
          <strong>{task.assigned_user_name}</strong>
        </div>
      )}
      {task.note && (
        <div className="stack" style={{ gap: 2 }}>
          <span className="field-label">Заметка</span>
          <span className="text-muted">{task.note}</span>
        </div>
      )}
      <button type="button" className="disclosure-link" onClick={toggleHistory}>
        {open ? 'Скрыть историю' : 'История изменений'}
      </button>
      {open && (
        <div className="stack" style={{ gap: 4 }}>
          {history === null ? (
            <span className="text-muted">Загрузка…</span>
          ) : history.length === 0 ? (
            <span className="text-muted">Записей нет</span>
          ) : (
            history.map((h) => (
              <div key={h.id} className="sale-history-row">
                <span>{h.action}</span>
                <span className="text-muted">{formatDateTime(h.created_at)}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

function NewTaskForm({
  user,
  employees,
  canAssignOthers,
  onDone,
}: {
  user: User | null
  employees: User[]
  canAssignOthers: boolean
  onDone: () => void
}) {
  const [title, setTitle] = useState('')
  const [note, setNote] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [assignedUserId, setAssignedUserId] = useState<number | null>(user?.id ?? null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const assigneeOptions = user
    ? [
        { value: String(user.id), label: 'Себе' },
        ...employees.filter((e) => e.id !== user.id).map((e) => ({ value: String(e.id), label: e.name })),
      ]
    : []

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    setError(null)
    setSaving(true)
    try {
      await createTask({
        title: title.trim(),
        assigned_user_id: assignedUserId,
        note,
        due_date: dueDate || null,
      })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать задачу')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="field">
        Название
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Позвонить поставщику" autoFocus />
      </label>
      {canAssignOthers && (
        <label className="field">
          Исполнитель
          <Select
            value={assignedUserId != null ? String(assignedUserId) : ''}
            onChange={(v) => setAssignedUserId(Number(v))}
            options={assigneeOptions}
          />
        </label>
      )}
      <label className="field">
        Срок
        <DateInput value={dueDate} onChange={setDueDate} />
      </label>
      <label className="field">
        Заметка
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="детали…" />
      </label>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving || !title.trim()}>
        {saving ? 'Сохранение…' : 'Создать задачу'}
      </Button>
    </form>
  )
}
