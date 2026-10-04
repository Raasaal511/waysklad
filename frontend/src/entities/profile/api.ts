import { api } from '../../shared/api/client'
import type { Role, TelegramStart, TokenResponse, User } from '../auth/api'

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
  input: {
    name: string
    role: Role
    is_active: boolean
    warehouse_ids?: number[] | null
    /** новый пароль — только когда владелец его меняет */
    password?: string
  },
) {
  return api.patch<User>(`/auth/employees/${employeeId}`, input)
}

export interface Tenant {
  id: number
  name: string
  slug: string | null
  storefront_enabled: boolean
  owner_telegram_chat_id: string | null
  summary_daily_enabled: boolean
  summary_weekly_enabled: boolean
  summary_monthly_enabled: boolean
  summary_daily_hour_msk: number
  logo: string
  storefront_show_stock_qty: boolean
  storefront_description: string
  contact_phone: string
  contact_whatsapp: string
  contact_telegram: string
  storefront_min_order_total: string | null
  policy_refund_money: string
  policy_payment: string
  policy_delivery: string
  policy_returns: string
}

/** Владелец, зарегистрированный до бота, подключает Telegram из профиля. */
export function startTelegramLink() {
  return api.post<TelegramStart>('/auth/telegram/link')
}

export function confirmTelegramLink(token: string, code: string) {
  return api.post<Tenant>('/auth/telegram/link/confirm', { token, code })
}

export function getShop() {
  return api.get<Tenant>('/auth/shop')
}

export interface UpdateShopInput {
  name: string
  storefront_enabled?: boolean
  summary_daily_enabled?: boolean
  summary_weekly_enabled?: boolean
  summary_monthly_enabled?: boolean
  summary_daily_hour_msk?: number
  storefront_show_stock_qty?: boolean
  storefront_description?: string
  contact_phone?: string
  contact_whatsapp?: string
  contact_telegram?: string
  storefront_min_order_total?: string | null
  policy_refund_money?: string
  policy_payment?: string
  policy_delivery?: string
  policy_returns?: string
}

export function updateShop(input: UpdateShopInput) {
  return api.patch<Tenant>('/auth/shop', input)
}

export function uploadShopLogo(file: File) {
  const form = new FormData()
  form.append('file', file)
  return api.postForm<Tenant>('/auth/shop/logo', form)
}

export function deleteShopLogo() {
  return api.delete<Tenant>('/auth/shop/logo')
}

export function changePassword(input: { current_password: string; new_password: string }) {
  return api.patch<TokenResponse>('/auth/me/password', input)
}

export function logoutAll() {
  return api.post<void>('/auth/me/logout-all')
}
