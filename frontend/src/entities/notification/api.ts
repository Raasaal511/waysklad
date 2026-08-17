import { api } from '../../shared/api/client'

export type NotificationKind = 'task_assigned' | 'task_done'

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
