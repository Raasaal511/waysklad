import type { OrderStatus } from './api'

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  new: 'Новый',
  in_progress: 'В работе',
  ready: 'Готов',
  issued: 'Выдан',
  cancelled: 'Отменён',
}

export const ORDER_STATUS_BADGE_CLASS: Record<OrderStatus, string> = {
  new: 'badge',
  in_progress: 'badge warning',
  ready: 'badge accent',
  issued: 'badge accent',
  cancelled: 'badge danger',
}

/** Кнопка «дальше» на карточке канбана. `ready → issued` — не смена статуса
 * напрямую, а сигнал открыть форму выдачи (см. OrdersPage.startIssuing). */
export const NEXT_STATUS: Record<OrderStatus, OrderStatus | null> = {
  new: 'in_progress',
  in_progress: 'ready',
  ready: 'issued',
  issued: null,
  cancelled: null,
}

export const BOARD_STATUSES: OrderStatus[] = ['new', 'in_progress', 'ready']

export const STATUS_ACCENT: Record<OrderStatus, string> = {
  new: 'var(--board-new)',
  in_progress: 'var(--board-progress)',
  ready: 'var(--board-ready)',
  issued: 'var(--board-ready)',
  cancelled: 'var(--danger)',
}
