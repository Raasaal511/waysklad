import { api } from './client'
import type { Role, User } from './auth'

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
