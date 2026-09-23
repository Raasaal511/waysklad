import { api } from '../../shared/api/client'
import { loadAdminToken } from './api'

/** Вкладка «Обратная связь» админки: обращения из кабинетов магазинов. */

export type AdminFeedbackTopic = 'question' | 'bug' | 'suggestion'
export type AdminFeedbackStatus = 'new' | 'resolved' | 'all'

export interface AdminFeedbackItem {
  id: number
  topic: AdminFeedbackTopic
  text: string
  photos: string[]
  page: string
  user_agent: string
  app_version: string
  created_at: string
  resolved_at: string | null
  tenant_id: number
  shop_name: string
  author_name: string
  author_phone: string
  author_role: string
}

export interface AdminFeedbackList {
  items: AdminFeedbackItem[]
  total: number
  /** Неразобранные всего — для счётчика, без учёта фильтра. */
  new_count: number
}

function headers(): HeadersInit {
  const token = loadAdminToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function getAdminFeedback(params: {
  status: AdminFeedbackStatus
  topic?: AdminFeedbackTopic
  limit?: number
}) {
  const query = new URLSearchParams({ status: params.status, limit: String(params.limit ?? 100) })
  if (params.topic) query.set('topic', params.topic)
  return api.get<AdminFeedbackList>(`/admin/feedback?${query}`, { headers: headers() })
}

export function resolveAdminFeedback(id: number, resolved = true) {
  return api.post<{ id: number; resolved: boolean }>(
    `/admin/feedback/${id}/resolve?resolved=${resolved}`,
    {},
    { headers: headers() },
  )
}
