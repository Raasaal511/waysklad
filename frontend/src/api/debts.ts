import { api } from './client'

export interface Debt {
  id: number
  client_id: number | null
  supplier_id: number | null
  amount: string
  repaid: string
  balance: string
  is_closed: boolean
  issued_at: string
  due_date: string | null
  sale_id: number | null
  note: string
}

export interface DebtsSummary {
  total_balance: string
  debts: Debt[]
}

export function issueDebt(input: { client_id: number; amount: string; due_date?: string | null; note?: string }) {
  return api.post<Debt>('/debts', input)
}

export function issueSupplierDebt(input: {
  supplier_id: number
  amount: string
  due_date?: string | null
  note?: string
}) {
  return api.post<Debt>('/debts/suppliers', input)
}

export function repayDebt(debtId: number, input: { amount: string; paid_on?: string | null }) {
  return api.post<Debt>(`/debts/${debtId}/repayments`, input)
}

export function listClientDebts(clientId: number) {
  return api.get<DebtsSummary>(`/debts/client/${clientId}`)
}

export function listSupplierDebts(supplierId: number) {
  return api.get<DebtsSummary>(`/debts/supplier/${supplierId}`)
}

export function listDueDebts(on?: string) {
  const q = on ? `?on=${on}` : ''
  return api.get<Debt[]>(`/debts/due${q}`)
}

export function createInstallment(
  debtId: number,
  schedule: { due_date: string; amount: string }[],
) {
  return api.post<Debt>(`/debts/${debtId}/installments`, { schedule })
}
