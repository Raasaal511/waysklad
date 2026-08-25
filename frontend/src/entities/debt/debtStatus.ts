import type { DebtStatus } from './api'

export const DEBT_STATUS_LABELS: Record<DebtStatus, string> = {
  active: 'Активен',
  due_soon: 'Скоро срок',
  overdue: 'Просрочен',
  partially_paid: 'Погашен частично',
  closed: 'Погашен',
}

export const DEBT_STATUS_BADGE_CLASS: Record<DebtStatus, string> = {
  active: 'badge',
  due_soon: 'badge warning',
  overdue: 'badge danger',
  partially_paid: 'badge warning',
  closed: 'badge accent',
}
