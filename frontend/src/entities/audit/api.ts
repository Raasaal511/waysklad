import { api } from '../../shared/api/client'

export interface AuditEntry {
  id: number
  user_id: number
  user_name: string | null
  action: string
  entity: string
  entity_id: number | null
  details: Record<string, unknown>
  created_at: string
}

export function listAudit(limit = 50, offset = 0) {
  return api.get<AuditEntry[]>(`/audit?limit=${limit}&offset=${offset}`)
}
