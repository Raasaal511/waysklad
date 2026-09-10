import {
  IconBrandInstagram,
  IconBrandWhatsapp,
  IconBuildingStore,
  IconMapPin,
  IconPhone,
  type Icon as TablerIcon,
} from '@tabler/icons-react'
import type { OrderSource, OrderHistoryEntry, OrderStatus } from '../../entities/order/api'
import { ORDER_STATUS_LABELS } from '../../entities/order/orderStatus'
import { formatMoney } from '../../shared/lib/format'

export const ORDER_SOURCE_LABELS: Record<OrderSource, string> = {
  whatsapp: 'WhatsApp',
  instagram: 'Instagram',
  call: 'Звонок',
  in_person: 'Очно',
  storefront: 'Витрина',
}

export const ORDER_SOURCE_ICONS: Record<OrderSource, TablerIcon> = {
  whatsapp: IconBrandWhatsapp,
  instagram: IconBrandInstagram,
  call: IconPhone,
  in_person: IconMapPin,
  storefront: IconBuildingStore,
}

export const ORDER_HISTORY_ACTION_LABELS: Record<string, string> = {
  'order.create': 'Заказ создан',
  'order.update': 'Изменён состав заказа',
  'order.status': 'Изменён статус',
  'order.cancel': 'Заказ отменён',
  'order.issue': 'Заказ выдан',
}

export function formatOrderHistoryDetail(entry: OrderHistoryEntry): string | null {
  const d = entry.details
  switch (entry.action) {
    case 'order.create':
    case 'order.update':
    case 'order.issue':
      return d.total != null ? `${formatMoney(String(d.total))} ₽` : null
    case 'order.status': {
      const status = d.status as OrderStatus | undefined
      return status ? ORDER_STATUS_LABELS[status] : null
    }
    case 'order.cancel':
      return typeof d.reason === 'string' && d.reason ? d.reason : null
    default:
      return null
  }
}

export function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDueDate(value: string) {
  const date = new Date(value)
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

export function isOverdue(dueDate: string) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return new Date(dueDate) < today
}
