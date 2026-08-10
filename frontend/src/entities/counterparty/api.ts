import { api } from '../../shared/api/client'

export interface Client {
  id: number
  name: string
  phone: string
  whatsapp: string
  city: string
  debt_limit: string | null
}

export interface Supplier {
  id: number
  name: string
  contact: string
  note: string
}

export function searchClients(query = '') {
  const q = query ? `?query=${encodeURIComponent(query)}` : ''
  return api.get<Client[]>(`/counterparties/clients${q}`)
}

export function createClient(input: {
  name: string
  phone?: string
  whatsapp?: string
  city?: string
  debt_limit?: string | null
}) {
  return api.post<Client>('/counterparties/clients', input)
}

export function listSuppliers() {
  return api.get<Supplier[]>('/counterparties/suppliers')
}

export function createSupplier(input: { name: string; contact?: string; note?: string }) {
  return api.post<Supplier>('/counterparties/suppliers', input)
}
