import { api } from '../../shared/api/client'

export const ADMIN_TOKEN_KEY = 'admin_access_token'

export function loadAdminToken(): string | null {
  return localStorage.getItem(ADMIN_TOKEN_KEY)
}

export function saveAdminToken(token: string) {
  localStorage.setItem(ADMIN_TOKEN_KEY, token)
}

export function clearAdminToken() {
  localStorage.removeItem(ADMIN_TOKEN_KEY)
}

function adminHeaders(): HeadersInit {
  const token = loadAdminToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function adminLogin(login: string, password: string) {
  return api.post<{ access_token: string; expires_in_minutes: number }>('/admin/login', {
    login,
    password,
  })
}

export interface AdminStatus {
  db_connected: boolean
  redis_connected: boolean
  active_users: number
  active_tenants: number
  online_now: number
  online_now_note: string
  cpu_percent: number
  memory_percent: number
  memory_used_mb: number
  memory_total_mb: number
}

export function getAdminStatus() {
  return api.get<AdminStatus>('/admin/status', { headers: adminHeaders() })
}

export interface AdminTenantListItem {
  id: number
  name: string
  slug: string | null
  storefront_enabled: boolean
  is_suspended: boolean
  created_at: string
}

export function listAdminTenants() {
  return api.get<{ tenants: AdminTenantListItem[] }>('/admin/tenants', { headers: adminHeaders() })
}

export interface AdminTenantDetail {
  id: number
  name: string
  slug: string | null
  storefront_enabled: boolean
  is_suspended: boolean
  created_at: string
  owner: { name: string; phone: string } | null
  users_count: number
  products_count: number
  warehouses_count: number
  last_sale_at: string | null
}

export function getAdminTenant(id: number) {
  return api.get<AdminTenantDetail>(`/admin/tenants/${id}`, { headers: adminHeaders() })
}

export function suspendAdminTenant(id: number) {
  return api.post<AdminTenantDetail>(`/admin/tenants/${id}/suspend`, undefined, {
    headers: adminHeaders(),
  })
}

export function unsuspendAdminTenant(id: number) {
  return api.post<AdminTenantDetail>(`/admin/tenants/${id}/unsuspend`, undefined, {
    headers: adminHeaders(),
  })
}

export interface AdminErrorLog {
  timestamp: string
  method: string
  path: string
  error_type: string
  message: string
}

export function getAdminErrorLogs(limit = 50) {
  return api.get<{ errors: AdminErrorLog[] }>(`/admin/error-logs?limit=${limit}`, {
    headers: adminHeaders(),
  })
}
