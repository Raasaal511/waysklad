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

export interface AdminRecentTenant {
  id: number
  name: string
  slug: string | null
  created_at: string
}

export interface AdminMetricsPoint {
  ts: number
  cpu_percent: number
  memory_percent: number
}

/** null означает «нет данных» (нет расширения БД, нет файла статуса) — не ноль. */
export interface AdminAppInfo {
  version: string
  git_sha: string
  started_at: string | null
  uptime_seconds: number | null
  workers: number
}

export interface AdminDbInfo {
  ok: boolean
  size_bytes: number | null
  connections_active: number | null
  connections_max: number | null
  slowest_query_ms_1h: number | null
}

export interface AdminRedisInfo {
  ok: boolean
  used_memory: number | null
  keys: number | null
  hit_rate_1h: number | null
}

export interface AdminUploadsInfo {
  files_count: number
  size_bytes: number
}

export interface AdminApiInfo {
  rps_1h: number | null
  p50_ms: number | null
  p95_ms: number | null
  errors_5xx_24h: number
  errors_4xx_24h: number
}

export interface AdminBackupInfo {
  last_at: string | null
  size_bytes: number | null
  /** false, пока внешняя копия не настроена */
  offsite_ok: boolean
}

export interface AdminTlsInfo {
  domain: string
  expires_at: string
  days_left: number
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
  disk_percent: number
  disk_used_gb: number
  disk_total_gb: number
  recent_tenants: AdminRecentTenant[]
  history: AdminMetricsPoint[]
  load_avg: number[] | null
  disk_free_percent: number | null
  app: AdminAppInfo | null
  db: AdminDbInfo | null
  redis: AdminRedisInfo | null
  uploads: AdminUploadsInfo | null
  api: AdminApiInfo | null
  backup: AdminBackupInfo | null
  tls: AdminTlsInfo | null
}

export function getAdminStatus() {
  return api.get<AdminStatus>('/admin/status', { headers: adminHeaders() })
}

export type TenantHealth = 'new' | 'active' | 'quiet' | 'churned'

export interface AdminTenantListItem {
  id: number
  name: string
  slug: string | null
  city: string | null
  created_at: string
  is_suspended: boolean
  is_verified: boolean
  storefront_enabled: boolean
  owner_name: string
  users_count: number
  warehouses_count: number
  products_count: number
  last_sale_at: string | null
  last_login_at: string | null
  sales_7d: number
  sales_30d: number
  sales_sum_30d: string
  debts_open_count: number
  storefront_requests_30d: number
  health: TenantHealth
}

export interface AdminTenantsParams {
  query?: string
  status?: string
  storefront?: 'on' | 'off'
  sort?: 'last_activity' | 'sales_30d' | 'created_at' | 'name'
  limit?: number
  offset?: number
}

export interface AdminTenantsResponse {
  tenants: AdminTenantListItem[]
  total: number
  /** счётчики для чипов фильтра — по всей платформе, не по текущей странице */
  counts_by_health: Record<string, number>
}

export function listAdminTenants(params: AdminTenantsParams = {}) {
  const search = new URLSearchParams()
  if (params.query) search.set('query', params.query)
  if (params.status && params.status !== 'all') search.set('status', params.status)
  if (params.storefront) search.set('storefront', params.storefront)
  if (params.sort) search.set('sort', params.sort)
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.offset != null) search.set('offset', String(params.offset))
  const qs = search.toString()
  return api.get<AdminTenantsResponse>(`/admin/tenants${qs ? `?${qs}` : ''}`, {
    headers: adminHeaders(),
  })
}

export interface AdminTenantUser {
  id: number
  name: string
  role: string
  is_active: boolean
  last_login_at: string | null
}

export interface AdminTenantWarehouse {
  id: number
  name: string
  address: string
  show_on_storefront: boolean
  positions_count: number
}

/** Только название и счётчик: выручка по товарам — содержимое чужого бизнеса. */
export interface AdminTenantTopProduct {
  id: number
  name: string
  sold_30d: string
}

export interface AdminTenantStorefront {
  enabled: boolean
  slug: string | null
  products_on_storefront: number
  requests_30d: number
  reviews_count: number
}

export interface AdminTenantActivity {
  at: string
  actor_name: string
  action: string
  entity: string
}

export interface AdminTenantSalesSeries {
  date: string[]
  count: number[]
  sum: string[]
}

export interface AdminTenantTotals {
  products: number
  sales_all_time: number
  debts_open_count: number
  customers_served: number
}

export interface AdminTenantDetail {
  id: number
  name: string
  slug: string | null
  city: string | null
  logo: string
  storefront_enabled: boolean
  is_suspended: boolean
  is_verified: boolean
  created_at: string
  owner: { name: string; phone: string } | null
  users_count: number
  products_count: number
  warehouses_count: number
  last_sale_at: string | null
  last_login_at: string | null
  health: TenantHealth
  sales_7d: number
  sales_30d: number
  sales_sum_30d: string
  sales_series_30d: AdminTenantSalesSeries | null
  users: AdminTenantUser[]
  warehouses: AdminTenantWarehouse[]
  top_products: AdminTenantTopProduct[]
  storefront: AdminTenantStorefront | null
  recent_activity: AdminTenantActivity[]
  totals: AdminTenantTotals | null
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


// --- Обзор платформы (A1) ---------------------------------------------------

export interface AdminOverviewSeries {
  /** массивы одной длины: date[i] соответствует остальным полям по индексу */
  date: string[]
  new_shops: number[]
  sales_count: number[]
  active_shops: number[]
}

export interface AdminOverview {
  shops: {
    total: number
    active_7d: number
    active_30d: number
    new_7d: number
    new_30d: number
    suspended: number
    storefront_on: number
  }
  users: { total: number; active_7d: number }
  customers: { total: number; new_7d: number }
  sales: {
    today_count: number
    today_sum: string
    d7_count: number
    d7_sum: string
    d30_count: number
    d30_sum: string
  }
  /** агрегат по платформе, без разбивки по клиентам магазинов */
  debts: { open_count: number; open_sum: string }
  storefront: { requests_7d: number; accepted_7d: number }
  series_30d: AdminOverviewSeries
}

export function getAdminOverview() {
  return api.get<AdminOverview>('/admin/overview', { headers: adminHeaders() })
}

// --- Ошибки: группы и детали (A5) -------------------------------------------

export interface AdminErrorGroup {
  signature: string
  type: string
  path: string
  method: string
  count_24h: number
  count_7d: number
  first_at: string
  last_at: string
  sample_id: number
}

export interface AdminErrorGroupsParams {
  /** период в сутках: 1 / 7 / 30 */
  periodDays?: number
  onlyUnresolved?: boolean
  errorType?: string
  path?: string
}

export function listAdminErrorGroups(params: AdminErrorGroupsParams = {}) {
  const search = new URLSearchParams()
  if (params.periodDays != null) search.set('period_days', String(params.periodDays))
  if (params.onlyUnresolved != null) search.set('only_unresolved', String(params.onlyUnresolved))
  if (params.errorType) search.set('error_type', params.errorType)
  if (params.path) search.set('path', params.path)
  const qs = search.toString()
  return api.get<AdminErrorGroup[]>(`/admin/error-groups${qs ? `?${qs}` : ''}`, {
    headers: adminHeaders(),
  })
}

export interface AdminErrorEntry {
  id: number
  at: string
  path: string
  method: string
  type: string
  message: string
  status: number | null
  tenant_id: number | null
  stack: string | null
}

export function listAdminErrorGroupEntries(signature: string, limit = 20) {
  return api.get<AdminErrorEntry[]>(
    `/admin/error-groups/${encodeURIComponent(signature)}/entries?limit=${limit}`,
    { headers: adminHeaders() },
  )
}

export function getAdminErrorEntry(id: number) {
  return api.get<AdminErrorEntry>(`/admin/error-logs/${id}`, { headers: adminHeaders() })
}

/** resolved=false возвращает группу обратно в список нерешённых. */
export function resolveAdminErrorGroup(signature: string, resolved = true) {
  return api.post<{ resolved: boolean; affected: number }>(
    `/admin/error-groups/${encodeURIComponent(signature)}/resolve?resolved=${resolved}`,
    {},
    { headers: adminHeaders() },
  )
}
