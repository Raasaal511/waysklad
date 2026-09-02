import { api } from '../../shared/api/client'
import type { Role, TokenResponse, User } from '../auth/api'

export function listEmployees() {
  return api.get<User[]>('/auth/employees')
}

export function createEmployee(input: {
  name: string
  phone: string
  password: string
  role: Role
  warehouse_ids?: number[]
}) {
  return api.post<User>('/auth/employees', input)
}

export function updateEmployee(
  employeeId: number,
  input: { name: string; role: Role; is_active: boolean; warehouse_ids?: number[] | null },
) {
  return api.patch<User>(`/auth/employees/${employeeId}`, input)
}

export interface Tenant {
  id: number
  name: string
  owner_telegram_chat_id: string | null
  summary_daily_enabled: boolean
  summary_weekly_enabled: boolean
  summary_monthly_enabled: boolean
  summary_daily_hour_msk: number
}

export function connectTelegram(chatId: string) {
  return api.post<Tenant>('/auth/telegram', { chat_id: chatId })
}

export function getShop() {
  return api.get<Tenant>('/auth/shop')
}

export interface UpdateShopInput {
  name: string
  summary_daily_enabled?: boolean
  summary_weekly_enabled?: boolean
  summary_monthly_enabled?: boolean
  summary_daily_hour_msk?: number
}

export function updateShop(input: UpdateShopInput) {
  return api.patch<Tenant>('/auth/shop', input)
}

export function changePassword(input: { current_password: string; new_password: string }) {
  return api.patch<TokenResponse>('/auth/me/password', input)
}

export function logoutAll() {
  return api.post<void>('/auth/me/logout-all')
}
