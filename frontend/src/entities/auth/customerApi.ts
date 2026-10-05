import { api } from '../../shared/api/client'

export const CUSTOMER_TOKEN_KEY = 'customer_access_token'

export function loadCustomerToken(): string | null {
  return localStorage.getItem(CUSTOMER_TOKEN_KEY)
}

export function saveCustomerToken(token: string) {
  localStorage.setItem(CUSTOMER_TOKEN_KEY, token)
}

export function clearCustomerToken() {
  localStorage.removeItem(CUSTOMER_TOKEN_KEY)
}

export function customerAuthHeader(): HeadersInit {
  const token = loadCustomerToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function requestCustomerLoginLink(phone: string) {
  return api.post<{ token: string; telegram_deep_link: string }>('/auth/customer/login-link', { phone })
}

export interface CustomerAccount {
  id: number
  phone: string
  name: string
}

/** Регистрация: аккаунт создаётся только после подтверждения номера в Telegram,
 *  поэтому в ответе не токен, а та же пара token + deep-link, что и при входе. */
export function registerCustomer(input: {
  username: string
  phone: string
  password: string
  password_confirm: string
  personal_data_consent: boolean
}) {
  return api.post<{ token: string; telegram_deep_link: string }>('/auth/customer/register', input)
}

/** Вход по паролю. login — username или телефон. */
export function loginCustomerWithPassword(login: string, password: string) {
  return api.post<{ access_token: string; customer: CustomerAccount }>('/auth/customer/login', {
    login,
    password,
  })
}

export function getCustomerLoginStatus(token: string) {
  return api.get<{ confirmed: boolean; access_token: string | null }>(
    `/auth/customer/login-status?token=${encodeURIComponent(token)}`,
  )
}

export interface CustomerProfile {
  id: number
  phone: string
  name: string
  username: string
  phone_verified: boolean
  phone_verified_at: string | null
  created_at: string | null
  has_password: boolean
  stats: {
    requests_total: number
    requests_accepted: number
    requests_rejected: number
    requests_active: number
    shops_count: number
  }
}

export interface CustomerShort {
  id: number
  phone: string
  name: string
  username: string
  phone_verified: boolean
}

export function getCustomerProfile() {
  return api.get<CustomerProfile>('/auth/customer/me', { headers: customerAuthHeader() })
}

/** Только имя: телефон приходит из контакта Telegram при входе. */
export function updateCustomerProfile(input: { name: string }) {
  return api.put<CustomerShort>('/auth/customer/me', input, { headers: customerAuthHeader() })
}

/** Смена номера: аккаунт не меняется, пока владелец нового номера не
 *  подтвердит его контактом в Telegram-боте по этой ссылке. */
export function requestCustomerPhoneChange(newPhone: string) {
  return api.post<{ token: string; telegram_deep_link: string }>(
    '/auth/customer/me/phone-change',
    { new_phone: newPhone },
    { headers: customerAuthHeader() },
  )
}

export function changeCustomerPassword(input: { new_password: string; current_password?: string }) {
  return api.patch<{ access_token: string }>(
    '/auth/customer/me/password',
    input,
    { headers: customerAuthHeader() },
  )
}

export function logoutCustomerEverywhere() {
  return api.post<void>('/auth/customer/me/logout-all', {}, { headers: customerAuthHeader() })
}

export interface MyRequestLine {
  product_id: number
  name: string
  photo: string
  quantity: string
  price: string
  total: string
}

export interface MyRequest {
  id: number
  status: 'new' | 'accepted' | 'rejected'
  customer_name: string
  customer_phone: string
  note: string
  created_at: string | null
  shop_name: string
  shop_slug: string
  shop_logo: string
  order_lines: MyRequestLine[]
  order_total: string
  due_date: string | null
  accepted_total: string | null
  prepayment: string | null
  to_pay: string | null
  order_status: string | null
  insufficient_stock_at_request: boolean
}

/** @deprecated используйте MyRequest — старое имя оставлено для совместимости импортов */
export type CustomerRequest = MyRequest

export function listMyStorefrontRequests(params: {
  status?: 'new' | 'accepted' | 'rejected'
  limit?: number
  offset?: number
} = {}) {
  const search = new URLSearchParams()
  if (params.status) search.set('status', params.status)
  if (params.limit != null) search.set('limit', String(params.limit))
  if (params.offset != null) search.set('offset', String(params.offset))
  const qs = search.toString()
  return api.get<{ items: MyRequest[]; total: number }>(
    `/storefront/requests/my${qs ? `?${qs}` : ''}`,
    { headers: customerAuthHeader() },
  )
}

export interface CustomerChatSummary {
  request_id: number
  shop_name: string
  shop_slug: string
  shop_logo: string
  request_status: string
  last_message: string
  last_message_at: string | null
  last_message_from_shop: boolean
  messages_count: number
}

export interface CustomerChatMessage {
  id: number | null
  request_id: number
  author: 'customer' | 'staff'
  text: string
  created_at: string | null
}

export function listCustomerChats() {
  return api.get<CustomerChatSummary[]>('/auth/customer/chats', {
    headers: customerAuthHeader(),
  })
}

export function listCustomerChatMessages(requestId: number) {
  return api.get<CustomerChatMessage[]>(`/auth/customer/chats/${requestId}`, {
    headers: customerAuthHeader(),
  })
}

export function sendCustomerChatMessage(requestId: number, text: string) {
  return api.post<CustomerChatMessage>(
    `/auth/customer/chats/${requestId}`,
    { text },
    { headers: customerAuthHeader() },
  )
}

/** Локально помечаем чат прочитанным — для бейджа «магазин ответил». */
const CHAT_SEEN_PREFIX = 'waysklad:chat-seen:'

export function markCustomerChatSeen(requestId: number, atIso: string | null) {
  if (!atIso) return
  try {
    localStorage.setItem(`${CHAT_SEEN_PREFIX}${requestId}`, atIso)
  } catch {
    /* ignore */
  }
}

export function isCustomerChatUnread(chat: CustomerChatSummary): boolean {
  if (!chat.last_message_from_shop || !chat.last_message_at) return false
  try {
    const seen = localStorage.getItem(`${CHAT_SEEN_PREFIX}${chat.request_id}`)
    if (!seen) return true
    return new Date(chat.last_message_at).getTime() > new Date(seen).getTime()
  } catch {
    return chat.last_message_from_shop
  }
}

export function countUnreadCustomerChats(chats: CustomerChatSummary[]): number {
  return chats.filter(isCustomerChatUnread).length
}

const PENDING_CHECKOUT_PREFIX = 'waysklad:pending-checkout:'

export function savePendingCheckout(slug: string, data: { name: string; note: string }) {
  try {
    sessionStorage.setItem(`${PENDING_CHECKOUT_PREFIX}${slug}`, JSON.stringify(data))
  } catch {
    /* ignore */
  }
}

export function takePendingCheckout(slug: string): { name: string; note: string } | null {
  try {
    const raw = sessionStorage.getItem(`${PENDING_CHECKOUT_PREFIX}${slug}`)
    if (!raw) return null
    sessionStorage.removeItem(`${PENDING_CHECKOUT_PREFIX}${slug}`)
    return JSON.parse(raw) as { name: string; note: string }
  } catch {
    return null
  }
}
