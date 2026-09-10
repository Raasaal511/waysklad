import { api } from '../../shared/api/client'

export interface Client {
  id: number
  name: string
  phone: string
  whatsapp: string
  city: string
  debt_limit: string | null
  is_active: boolean
}

export interface Supplier {
  id: number
  name: string
  contact: string
  note: string
}

export function searchClients(query = '', includeInactive = false) {
  const params = new URLSearchParams()
  if (query) params.set('query', query)
  if (includeInactive) params.set('include_inactive', 'true')
  const q = params.toString()
  return api.get<Client[]>(`/counterparties/clients${q ? `?${q}` : ''}`)
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

export function updateClient(
  clientId: number,
  input: {
    name: string
    phone?: string
    whatsapp?: string
    city?: string
    debt_limit?: string | null
    is_active: boolean
    force?: boolean
  },
) {
  return api.patch<Client>(`/counterparties/clients/${clientId}`, input)
}

export function listSuppliers() {
  return api.get<Supplier[]>('/counterparties/suppliers')
}

export function createSupplier(input: { name: string; contact?: string; note?: string }) {
  return api.post<Supplier>('/counterparties/suppliers', input)
}

export interface ClientSummary {
  client: Client
  debt_balance: string
  active_orders_count: number
  open_tasks_count: number
}

export type ClientTimelineEventType =
  | 'sale'
  | 'order_created'
  | 'order_status'
  | 'debt_issued'
  | 'debt_repaid'
  | 'debt_extended'
  | 'task'

export interface ClientTimelineEvent {
  type: ClientTimelineEventType
  occurred_at: string
  entity_id: number
  title: string
  amount: string | null
  status: string | null
}

export function getClient(clientId: number) {
  return api.get<ClientSummary>(`/counterparties/clients/${clientId}`)
}

export function getClientTimeline(clientId: number) {
  return api.get<ClientTimelineEvent[]>(`/counterparties/clients/${clientId}/timeline`)
}
