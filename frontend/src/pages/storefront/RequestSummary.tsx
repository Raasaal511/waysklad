import type { MyRequest } from '../../entities/auth/customerApi'
import { formatMoney, formatQuantity } from '../../shared/lib/format'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import styles from './RequestSummary.module.css'

function formatDay(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
}

/**
 * Состав заказа покупателя: что заказано, сколько и на какую сумму, а после
 * подтверждения — когда забрать и сколько доплатить. Один блок для страницы
 * «Заказ отправлен» и раскрытой строки в профиле → Заказы (там был голый
 * список «Название × 2»).
 */
export function RequestSummary({ req }: { req: MyRequest }) {
  const accepted = req.status === 'accepted'
  const total = accepted && req.accepted_total != null ? req.accepted_total : req.order_total

  return (
    <div className={styles.summary}>
      <ul className={styles.lines}>
        {req.order_lines.map((line) => (
          <li key={`${line.product_id}-${line.name}`} className={styles.line}>
            <ProductPhoto src={line.photo} size={48} />
            <div className={styles.lineBody}>
              <span className={styles.lineName}>{line.name}</span>
              <span className={styles.lineMeta}>
                {formatQuantity(line.quantity)} × {formatMoney(line.price)} ₽
              </span>
            </div>
            <span className={styles.lineTotal}>{formatMoney(line.total)} ₽</span>
          </li>
        ))}
      </ul>

      <div className={styles.totalRow}>
        <span>{accepted ? 'Сумма заказа' : 'Итого'}</span>
        <strong>{formatMoney(total)} ₽</strong>
      </div>

      {accepted && (req.due_date || req.to_pay) && (
        <dl className={styles.facts}>
          {req.due_date && (
            <div>
              <dt>Можно забрать</dt>
              <dd>{formatDay(req.due_date)}</dd>
            </div>
          )}
          {req.prepayment && Number(req.prepayment) > 0 && (
            <div>
              <dt>Предоплата</dt>
              <dd>{formatMoney(req.prepayment)} ₽</dd>
            </div>
          )}
          {req.to_pay && (
            <div>
              <dt>Доплатить при получении</dt>
              <dd>{formatMoney(req.to_pay)} ₽</dd>
            </div>
          )}
        </dl>
      )}

      {req.note && <p className={styles.note}>Ваш комментарий: {req.note}</p>}
    </div>
  )
}
