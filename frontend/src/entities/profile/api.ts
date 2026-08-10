import { api } from '../../shared/api/client'
import type { Role, User } from '../auth/api'

export function listEmployees() {
  return api.get<User[]>('/auth/employees')
}

export function createEmployee(input: {
  name: string
  phone: string
  password: string
  role: Role
}) {
  return api.post<User>('/auth/employees', input)
}

export interface Tenant {
  id: number
  name: string
  owner_telegram_chat_id: string | null
}

export function connectTelegram(chatId: string) {
  return api.post<Tenant>('/auth/telegram', { chat_id: chatId })
}

export function getShop() {
  return api.get<Tenant>('/auth/shop')
}

export function updateShop(input: { name: string }) {
  return api.patch<Tenant>('/auth/shop', input)
}

export function changePassword(input: { current_password: string; new_password: string }) {
  return api.patch<void>('/auth/me/password', input)
}
