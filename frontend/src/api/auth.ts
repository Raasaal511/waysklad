import { api } from './client'

export type Role = 'owner' | 'manager' | 'seller' | 'storekeeper' | 'analyst'

export interface User {
  id: number
  name: string
  phone: string
  role: Role
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

export function registerShop(input: {
  shop_name: string
  owner_name: string
  phone: string
  password: string
}) {
  return api.post<TokenResponse>('/auth/register', input)
}
