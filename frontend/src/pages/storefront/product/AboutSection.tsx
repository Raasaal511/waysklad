import { ExpandableText } from '../../../shared/ui/ExpandableText'
import type { StorefrontProductDetail } from '../../../entities/storefront/api'
import { formatQuantity, plural } from '../../../shared/lib/format'
import pageStyles from './ProductPage.module.css'
import styles from './AboutSection.module.css'

interface SpecRow {
  label: string
  value: string
}

function buildSpecs(product: StorefrontProductDetail): SpecRow[] {
  const specs: SpecRow[] = []
  if (product.sku) specs.push({ label: 'Артикул', value: product.sku })
  if (product.category) specs.push({ label: 'Категория', value: product.category.name })
  if (product.unit_label) specs.push({ label: 'Единица', value: product.unit_label })
  const colors = Array.from(new Set(product.variants.map((v) => v.color).filter(Boolean)))
  if (colors.length > 0) specs.push({ label: 'Цвета', value: colors.join(', ') })
  const sizes = Array.from(new Set(product.variants.map((v) => v.size).filter(Boolean)))
  if (sizes.length > 0) specs.push({ label: 'Размеры', value: sizes.join(', ') })
  if (product.min_order_qty) specs.push({ label: 'Мин. заказ', value: `${product.min_order_qty} ${product.unit_label}` })
  if (product.order_step_qty) specs.push({ label: 'Шаг заказа', value: `${product.order_step_qty} ${product.unit_label}` })
  return specs
}

const VIEWS_THRESHOLD = 10

/** «О товаре» — описание + компактная таблица характеристик, и просмотры за 90 дней под ней. */
export function AboutSection({ product }: { product: StorefrontProductDetail }) {
  const description = product.description?.trim()
  const specs = buildSpecs(product)
  const showViews = product.views_90d >= VIEWS_THRESHOLD

  if (!description && specs.length === 0) return null

  return (
    <div className={pageStyles.card}>
      {description ? (
        <ExpandableText
          title="О товаре"
          text={description}
          extra={
            <>
              {specs.length > 0 && (
                <div className={styles.specs}>
                  {specs.map((s) => (
                    <div key={s.label} className={styles.specRow}>
                      <span className={styles.specName}>{s.label}</span>
                      <span className={styles.specDots} />
                      <span className={styles.specValue}>{s.value}</span>
                    </div>
                  ))}
                </div>
              )}
              {showViews && (
                <p className={styles.views}>
                  {formatQuantity(product.views_90d)} {plural(product.views_90d, ['просмотр', 'просмотра', 'просмотров'])} за
                  90 дней
                </p>
              )}
            </>
          }
        />
      ) : (
        <>
          <h2 className={pageStyles.sectionTitle}>О товаре</h2>
          <div className={styles.specs}>
            {specs.map((s) => (
              <div key={s.label} className={styles.specRow}>
                <span className={styles.specName}>{s.label}</span>
                <span className={styles.specDots} />
                <span className={styles.specValue}>{s.value}</span>
              </div>
            ))}
          </div>
          {showViews && (
            <p className={styles.views}>
              {formatQuantity(product.views_90d)} {plural(product.views_90d, ['просмотр', 'просмотра', 'просмотров'])} за 90
              дней
            </p>
          )}
        </>
      )}
    </div>
  )
}
