import { useEffect, useState } from 'react'
import { IconHistory } from '@tabler/icons-react'
import { listAudit, type AuditEntry } from '../../entities/audit/api'
import { ApiError } from '../../shared/api/client'
import { Button } from '../../shared/ui/Button'

const PAGE_SIZE = 50

// Человекочитаемые подписи для action — see backend/app/application/**/*.py (AuditEntry.record)
const AUDIT_ACTION_LABELS: Record<string, string> = {
  'category.create': 'Создана категория',
  'client.create': 'Добавлен клиент',
  'debt.extend': 'Продлён срок долга',
  'debt.installment': 'Составлен график рассрочки',
  'debt.issue': 'Выдан долг клиенту',
  'debt.issue_supplier': 'Выдан долг поставщику',
  'debt.repay': 'Внесена оплата долга',
  'order.create': 'Создан заказ',
  'order.status': 'Изменён статус заказа',
  'product.create': 'Создан товар',
  'product.import': 'Импорт товаров из Excel',
  'product.set_photo': 'Изменено фото товара',
  'product.update': 'Изменён товар',
  'sale.create': 'Оформлена продажа',
  'sale.delete': 'Удалена продажа',
  'sale.edit': 'Изменена продажа',
  'sale.return': 'Оформлен возврат',
  'shop.connect_telegram': 'Подключён Telegram',
  'shop.register': 'Регистрация магазина',
  'shop.update': 'Изменены настройки магазина',
  'stock.receive': 'Приёмка товара',
  'stock.stocktake': 'Инвентаризация',
  'stock.transfer': 'Перемещение между складами',
  'stock.write_off': 'Списание товара',
  'supplier.create': 'Добавлен поставщик',
  'unit.create': 'Создана единица измерения',
  'user.change_password': 'Смена пароля',
  'user.create': 'Добавлен сотрудник',
  'warehouse.create': 'Создан склад',
  'warehouse.set_assignments': 'Изменена привязка кладовщиков к складу',
}

function actionLabel(action: string): string {
  return AUDIT_ACTION_LABELS[action] ?? action
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(true)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const page = await listAudit(PAGE_SIZE, 0)
      setEntries(page)
      setHasMore(page.length === PAGE_SIZE)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить журнал действий')
    } finally {
      setLoading(false)
    }
  }

  async function loadMore() {
    setLoadingMore(true)
    try {
      const page = await listAudit(PAGE_SIZE, entries.length)
      setEntries((prev) => [...prev, ...page])
      setHasMore(page.length === PAGE_SIZE)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить журнал действий')
    } finally {
      setLoadingMore(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Журнал действий</h2>
      </div>

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : entries.length === 0 ? (
        <p className="text-muted">Действий пока нет</p>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Дата и время</th>
                  <th>Сотрудник</th>
                  <th>Действие</th>
                  <th>Объект</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>{formatDateTime(entry.created_at)}</td>
                    <td>{entry.user_name ?? `#${entry.user_id}`}</td>
                    <td>
                      <span className="row" style={{ gap: 6 }}>
                        <IconHistory size={16} stroke={1.8} />
                        {actionLabel(entry.action)}
                      </span>
                    </td>
                    <td className="text-muted">
                      {entry.entity}
                      {entry.entity_id != null ? ` #${entry.entity_id}` : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hasMore && (
            <Button variant="secondary" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? 'Загрузка…' : 'Показать ещё'}
            </Button>
          )}
        </>
      )}
    </div>
  )
}
