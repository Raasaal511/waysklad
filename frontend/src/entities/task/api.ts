import { api } from '../../shared/api/client'

export type TaskType = 'general' | 'restock'
export type TaskStatus = 'new' | 'in_progress' | 'done'

export interface Task {
  id: number
  number: number | null
  title: string
  type: TaskType
  status: TaskStatus
  assigned_user_id: number | null
  assigned_user_name: string | null
  created_by_id: number | null
  created_by_name: string | null
  note: string
  due_date: string | null
  product_id: number | null
  warehouse_id: number | null
  quantity: string | null
  created_at: string | null
  completed_at: string | null
}

export interface TaskHistoryEntry {
  id: number
  user_id: number
  user_name: string | null
  action: string
  entity: string
  entity_id: number | null
  details: Record<string, unknown>
  created_at: string
}

export interface TaskCreateInput {
  title: string
  type?: TaskType
  assigned_user_id?: number | null
  note?: string
  due_date?: string | null
  product_id?: number | null
  warehouse_id?: number | null
  quantity?: string | null
}

export function listActiveTasks() {
  return api.get<Task[]>('/tasks')
}

export function listCompletedTasks() {
  return api.get<Task[]>('/tasks/completed')
}

export function getTask(id: number) {
  return api.get<Task>(`/tasks/${id}`)
}

export function createTask(input: TaskCreateInput) {
  return api.post<Task>('/tasks', input)
}

export function changeTaskStatus(id: number, newStatus: TaskStatus) {
  return api.patch<Task>(`/tasks/${id}/status`, { new_status: newStatus })
}

export interface TaskUpdateInput {
  assigned_user_id?: number | null
  due_date?: string | null
  note?: string
}

export function updateTask(id: number, input: TaskUpdateInput) {
  return api.patch<Task>(`/tasks/${id}`, input)
}

export function getTaskHistory(id: number) {
  return api.get<TaskHistoryEntry[]>(`/tasks/${id}/history`)
}
