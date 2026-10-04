import { api } from '../../shared/api/client'

export type Role = 'owner' | 'manager' | 'seller' | 'storekeeper' | 'analyst'

export interface User {
  id: number
  name: string
  phone: string
  role: Role
  is_active: boolean
  warehouse_ids: number[]
  /** Telegram подтверждён ботом: регистрация или подключение из профиля */
  telegram_verified?: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
  shop_slug: string | null
}

export function login(phone: string, password: string) {
  return api.post<TokenResponse>('/auth/login', { phone, password })
}

/** Шаг «подтвердите в Telegram»: ссылка на бота и до когда она живёт. */
export interface TelegramStart {
  token: string
  telegram_link: string
  expires_at: string
}

export interface TelegramVerificationStatus {
  contact_confirmed: boolean
  completed: boolean
  expired: boolean
  expires_at: string
  code_sent_at: string | null
}

/** Шаг 1: форма проверена, магазин создаётся только после кода из Telegram. */
export function registerShop(input: {
  shop_name: string
  owner_name: string
  phone: string
  password: string
  personal_data_consent: boolean
}) {
  return api.post<TelegramStart>('/auth/register', input)
}

/** Шаг 2: код из бота → магазин создан, сразу вход. */
export function confirmRegistration(token: string, code: string) {
  return api.post<TokenResponse>('/auth/register/confirm', { token, code })
}

export function getTelegramVerification(token: string) {
  return api.get<TelegramVerificationStatus>(`/auth/telegram/verification?token=${encodeURIComponent(token)}`)
}

export function resendTelegramCode(token: string) {
  return api.post<void>('/auth/telegram/verification/resend', { token })
}
