import { api } from '../../shared/api/client'

export type NotificationKind =
  | 'task_assigned'
  | 'task_done'
  | 'debt_due_soon'
  | 'debt_overdue'
  | 'debt_issued'
  | 'low_stock'
  | 'storefront_message'
  | 'storefront_request_new'

export function notificationsWsUrl(token: string): string {
  const apiBase = import.meta.env.VITE_API_URL ?? '/api'
  if (apiBase.startsWith('http')) {
    const wsBase = apiBase.replace(/^http/, 'ws')
    return `${wsBase}/notifications/ws?token=${encodeURIComponent(token)}`
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${apiBase}/notifications/ws?token=${encodeURIComponent(token)}`
}

export interface Notification {
  id: number
  kind: NotificationKind
  text: string
  link: string
  entity_id: number | null
  is_read: boolean
  created_at: string | null
}

export interface NotificationListResponse {
  items: Notification[]
  unread: number
}

export function listNotifications() {
  return api.get<NotificationListResponse>('/notifications')
}

export function markNotificationRead(id: number) {
  return api.post<Notification>(`/notifications/${id}/read`)
}

export function markAllNotificationsRead() {
  return api.post<{ marked: number }>('/notifications/read-all')
}
