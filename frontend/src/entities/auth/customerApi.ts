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

export function updateCustomerProfile(input: { name: string; phone?: string | null }) {
  return api.put<CustomerShort>('/auth/customer/me', input, { headers: customerAuthHeader() })
}

export function requestCustomerPhoneCode() {
  return api.post<{
    sent_via: 'telegram' | 'console'
    retry_after: number
    telegram_deep_link: string
  }>('/auth/customer/phone/request-code', {}, { headers: customerAuthHeader() })
}

export function verifyCustomerPhoneCode(code: string) {
  return api.post<{ phone_verified: boolean; phone_verified_at: string | null }>(
    '/auth/customer/phone/verify',
    { code },
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
