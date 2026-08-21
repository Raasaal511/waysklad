import { api } from '../../shared/api/client'

export type DebtStatus = 'active' | 'due_soon' | 'overdue' | 'partially_paid' | 'closed'

export interface DebtInstallment {
  due_date: string
  amount: string
}

export interface DebtRepayment {
  amount: string
  on: string
  note: string
  author_id: number | null
}

export interface DebtExtension {
  old_due_date: string | null
  new_due_date: string
  reason: string
  author_id: number | null
  created_at: string
}

export interface Debt {
  id: number
  client_id: number | null
  supplier_id: number | null
  amount: string
  repaid: string
  balance: string
  is_closed: boolean
  status: DebtStatus
  issued_at: string
  due_date: string | null
  sale_id: number | null
  receipt_document_id: number | null
  note: string
  schedule: DebtInstallment[]
  repayments: DebtRepayment[]
  extensions: DebtExtension[]
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

export function repayDebt(
  debtId: number,
  input: { amount: string; paid_on?: string | null; note?: string },
) {
  return api.post<Debt>(`/debts/${debtId}/repayments`, input)
}

export function extendDebt(debtId: number, input: { new_due_date: string; reason?: string }) {
  return api.post<Debt>(`/debts/${debtId}/extend`, input)
}

export function getDebt(debtId: number) {
  return api.get<Debt>(`/debts/${debtId}`)
}

export interface DebtHistoryEntry {
  id: number
  user_id: number
  action: string
  entity: string
  entity_id: number | null
  details: Record<string, unknown>
  created_at: string
}

export function getDebtHistory(debtId: number) {
  return api.get<DebtHistoryEntry[]>(`/debts/${debtId}/history`)
}

export function listActiveDebts() {
  return api.get<Debt[]>('/debts')
}

export function listClosedDebts() {
  return api.get<Debt[]>('/debts/closed')
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
