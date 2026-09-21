import { api } from '../../shared/api/client'
import type { StorefrontRequest } from '../storefront/api'

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

export interface CustomerRequest extends StorefrontRequest {
  shop_name: string
}

export function listMyStorefrontRequests() {
  return api.get<CustomerRequest[]>('/storefront/requests/my', {
    headers: customerAuthHeader(),
  })
}
