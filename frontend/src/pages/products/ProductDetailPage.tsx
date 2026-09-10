import { useEffect, useState, type CSSProperties } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  getProduct,
  getProductHistory,
  type Product,
} from '../../entities/product/api'
import { useCatalog } from '../../app/CatalogContext'
import { useAuth } from '../../app/AuthContext'
import { ApiError } from '../../shared/api/client'
import { IconButton } from '../../shared/ui/IconButton'
import { InfoHint } from '../../shared/ui/InfoHint'
import { HistoryDisclosure } from '../../shared/ui/HistoryDisclosure'
import { StockWarningIcon } from '../../shared/ui/StockWarningIcon'
import { formatMoney, formatQuantity, isLowStock, isOutOfStock } from '../../shared/lib/format'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './ProductDetailPage.module.css'
import {
  IconChevronLeft,
  IconChevronRight,
  IconPencil,
  IconCheck,
  IconPhoto,
  IconBarcode,
  IconPackage,
  IconCoin,
  IconPercentage,
  IconAlertTriangle,
  IconBuildingStore,
  IconShoppingBag,
  type Icon as TablerIcon,
} from '@tabler/icons-react'

const PRODUCT_HISTORY_ACTION_LABELS: Record<string, string> = {
  'product.create': 'Товар создан',
  'product.update': 'Изменены данные товара',
  'product.set_photo': 'Обновлено фото',
}

const PRODUCT_HISTORY_ACTION_ICONS: Record<string, TablerIcon> = {
  'product.create': IconCheck,
  'product.update': IconPencil,
  'product.set_photo': IconPhoto,
}

const STOCK_COLUMNS = '2fr 1fr 16px'
const VARIANT_COLUMNS = '1fr 1fr 1.4fr'

export function ProductDetailPage() {
  const { id } = useParams<{ id: string }>()
  const productId = Number(id)
  const navigate = useNavigate()
  const { user } = useAuth()
  const canManage = user?.role === 'owner' || user?.role === 'manager'

  const {
    categories,
    units,
    warehouses,
    stock,
    ensureCategories,
    ensureUnits,
    ensureWarehouses,
    ensureStock,
  } = useCatalog()

  const [product, setProduct] = useState<Product | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    ensureCategories().catch(() => {})
    ensureUnits().catch(() => {})
    ensureWarehouses().catch(() => {})
    ensureStock().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!Number.isFinite(productId) || productId <= 0) {
      setProduct(null)
      setError('Товар не найден')
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    getProduct(productId)
      .then((p) => {
        if (!cancelled) setProduct(p)
      })
      .catch((err) => {
        if (cancelled) return
        setProduct(null)
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить товар')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [productId])

  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code
  const categoryName =
    product?.category_id == null
      ? null
      : categories.find((c) => c.id === product.category_id)?.name ?? null

  const stockByWarehouse = product
    ? warehouses
        .map((w) => {
          const rows = stock.filter((s) => s.product_id === product.id && s.warehouse_id === w.id)
          return {
            warehouse: w,
            quantity: rows.reduce((sum, s) => sum + Number(s.quantity), 0),
            reserved: rows.reduce((sum, s) => sum + Number(s.reserved), 0),
          }
        })
        .filter((row) => row.quantity > 0 || warehouses.length <= 5)
    : []

  const totalStock = stockByWarehouse.reduce((sum, row) => sum + row.quantity, 0)
  const totalReserved = stockByWarehouse.reduce((sum, row) => sum + row.reserved, 0)
  const out = product ? isOutOfStock(totalStock) : false
  const low = product ? isLowStock(totalStock, product.min_stock) : false

  if (!loading && !product) {
    return (
      <div className={layoutStyles.stack}>
        <Link to="/products" className={layoutStyles.backLink}>
          <IconChevronLeft size={16} stroke={1.8} /> Все товары
        </Link>
        <p className={layoutStyles.error}>{error ?? 'Товар не найден'}</p>
      </div>
    )
  }

  return (
    <div className={layoutStyles.stack}>
      <Link to="/products" className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> Все товары
      </Link>

      {loading || !product ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : (
        <>
          <section className={`${styles.hero} ${styles.heroWithMedia} ${styles.reveal}`} style={{ '--reveal-delay': '0ms' } as CSSProperties}>
            {product.photo ? (
              <img src={product.photo} alt="" className={styles.heroPhoto} />
            ) : (
              <div className={`${styles.heroPhoto} ${styles.heroPhotoEmpty}`}>
                <IconPhoto size={48} stroke={1.4} />
              </div>
            )}
            <div className={styles.heroBody}>
              <div className={styles.heroTop}>
                <div className={styles.heroHeading}>
                  <h2 className={styles.heroTitle}>{product.name}</h2>
                  <div className={styles.heroTags}>
                    {categoryName && <span className="badge accent">{categoryName}</span>}
                    {product.sku && <span className={styles.skuChip}>Артикул {product.sku}</span>}
                    {product.show_on_storefront && (
                      <span className={styles.storefrontChip}>
                        <IconShoppingBag size={13} stroke={1.8} /> На витрине
                      </span>
                    )}
                  </div>
                </div>
                {canManage && (
                  <IconButton
                    variant="muted"
                    size="lg"
                    tooltip="Редактировать товар"
                    aria-label="Редактировать товар"
                    onClick={() => navigate(`/products/${product.id}/edit`)}
                  >
                    <IconPencil size={22} stroke={1.8} />
                  </IconButton>
                )}
              </div>
              <div className={styles.heroPrice}>
                {formatMoney(product.retail_price)}
                <span className={styles.heroPriceCurrency}>₽</span>
              </div>
              <div className={styles.heroMeta}>
                <span>
                  <IconBarcode size={15} stroke={1.8} />
                  {product.barcode || 'Без штрихкода'}
                </span>
                <span>
                  <IconPackage size={15} stroke={1.8} />
                  {unitName(product.unit_code)}
                </span>
              </div>
            </div>
          </section>

          <section
            className={`${styles.metrics} ${styles.reveal}`}
            style={{ '--reveal-delay': '60ms' } as CSSProperties}
          >
            <div className={styles.metric}>
              <span className={`${styles.metricIcon} ${out ? styles.metricIconDanger : low ? styles.metricIconWarn : ''}`}>
                {low || out ? <IconAlertTriangle size={18} stroke={1.8} /> : <IconPackage size={18} stroke={1.8} />}
              </span>
              <div className={styles.metricBody}>
                <strong>
                  {formatQuantity(String(totalStock))}{' '}
                  <span className={styles.metricCurrency}>{unitName(product.unit_code)}</span>
                  {low && <StockWarningIcon />}
                </strong>
                <span>
                  Остаток
                  {totalReserved > 0 && (
                    <InfoHint
                      text={`${formatQuantity(String(totalReserved))} в резерве под заказы — недоступно для продажи.`}
                    />
                  )}
                </span>
              </div>
            </div>
            {product.purchase_price !== null && (
              <div className={styles.metric}>
                <span className={styles.metricIcon}>
                  <IconCoin size={18} stroke={1.8} />
                </span>
                <div className={styles.metricBody}>
                  <strong>
                    {formatMoney(product.purchase_price)}
                    <span className={styles.metricCurrency}> ₽</span>
                  </strong>
                  <span>Закупка</span>
                </div>
              </div>
            )}
            {product.margin !== null && (
              <div className={styles.metric}>
                <span className={styles.metricIcon}>
                  <IconPercentage size={18} stroke={1.8} />
                </span>
                <div className={styles.metricBody}>
                  <strong>
                    {formatMoney(product.margin)}
                    <span className={styles.metricCurrency}> ₽</span>
                  </strong>
                  <span>Маржа</span>
                </div>
              </div>
            )}
            <div className={styles.metric}>
              <span className={styles.metricIcon}>
                <IconAlertTriangle size={18} stroke={1.8} />
              </span>
              <div className={styles.metricBody}>
                <strong>
                  {formatQuantity(product.min_stock)}{' '}
                  <span className={styles.metricCurrency}>{unitName(product.unit_code)}</span>
                </strong>
                <span>Мин. остаток</span>
              </div>
            </div>
            <div className={styles.metric}>
              <span className={styles.metricIcon}>
                <IconBuildingStore size={18} stroke={1.8} />
              </span>
              <div className={styles.metricBody}>
                <strong>{warehouses.length}</strong>
                <span>{warehouses.length === 1 ? 'Склад' : 'Складов'}</span>
              </div>
            </div>
          </section>

          <section className={`${styles.section} ${styles.reveal}`} style={{ '--reveal-delay': '110ms' } as CSSProperties}>
            <h3 className={styles.sectionTitle}>Остатки по складам</h3>
            {stockByWarehouse.length === 0 ? (
              <p className={layoutStyles.textMuted}>Остатков нет</p>
            ) : (
              <div className={layoutStyles.dataTable}>
                <div className={layoutStyles.dataTableHead} style={{ gridTemplateColumns: STOCK_COLUMNS }}>
                  <span>Склад</span>
                  <span>Остаток</span>
                </div>
                <div className={layoutStyles.dataTableBody}>
                  {stockByWarehouse.map((row, i) => (
                    <button
                      key={row.warehouse.id}
                      type="button"
                      className={`${layoutStyles.dataRow} ${layoutStyles.dataRowLink} ${styles.rowIn}`}
                      style={
                        {
                          gridTemplateColumns: STOCK_COLUMNS,
                          '--row-delay': `${Math.min(i, 12) * 25}ms`,
                        } as CSSProperties
                      }
                      onClick={() => navigate(`/stock/${row.warehouse.id}`)}
                    >
                      <span className={layoutStyles.dataRowName}>{row.warehouse.name}</span>
                      <span>
                        {row.quantity === 0 ? (
                          <span className={layoutStyles.textMuted}>Нет в наличии</span>
                        ) : (
                          <>
                            {formatQuantity(String(row.quantity))} {unitName(product.unit_code)}
                          </>
                        )}
                        {row.reserved > 0 && (
                          <span className={layoutStyles.textMuted}>
                            {' '}
                            (резерв {formatQuantity(String(row.reserved))})
                            <InfoHint text="Зарезервировано под заказы клиентов и недоступно для продажи — освободится, когда заказ выдадут или отменят." />
                          </span>
                        )}
                      </span>
                      <IconChevronRight size={14} stroke={1.8} className={layoutStyles.dataRowChevron} />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </section>

          {product.variants.length > 0 && (
            <section className={`${styles.section} ${styles.reveal}`} style={{ '--reveal-delay': '150ms' } as CSSProperties}>
              <h3 className={styles.sectionTitle}>Варианты</h3>
              <div className={layoutStyles.dataTable}>
                <div className={layoutStyles.dataTableHead} style={{ gridTemplateColumns: VARIANT_COLUMNS }}>
                  <span>Размер</span>
                  <span>Цвет</span>
                  <span>Штрихкод</span>
                </div>
                <div className={layoutStyles.dataTableBody}>
                  {product.variants.map((v, i) => (
                    <div
                      key={v.id}
                      className={`${layoutStyles.dataRow} ${styles.rowIn}`}
                      style={
                        {
                          gridTemplateColumns: VARIANT_COLUMNS,
                          '--row-delay': `${Math.min(i, 12) * 25}ms`,
                        } as CSSProperties
                      }
                    >
                      <span>{v.size || '—'}</span>
                      <span>{v.color || '—'}</span>
                      <span className={layoutStyles.textMuted}>{v.barcode || '—'}</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {(product.storefront_min_qty || product.storefront_step_qty) && (
            <section className={`${styles.section} ${styles.reveal}`} style={{ '--reveal-delay': '180ms' } as CSSProperties}>
              <h3 className={styles.sectionTitle}>Витрина</h3>
              <div className={styles.metaGrid}>
                <div className={styles.metaItem}>
                  <span className={layoutStyles.textMuted}>Мин. заказ</span>
                  <span>{product.storefront_min_qty ? formatQuantity(product.storefront_min_qty) : '—'}</span>
                </div>
                <div className={styles.metaItem}>
                  <span className={layoutStyles.textMuted}>Шаг заказа</span>
                  <span>{product.storefront_step_qty ? formatQuantity(product.storefront_step_qty) : '—'}</span>
                </div>
              </div>
            </section>
          )}

          <div className={styles.reveal} style={{ '--reveal-delay': '200ms' } as CSSProperties}>
            <HistoryDisclosure
              load={() => getProductHistory(product.id)}
              actionLabels={PRODUCT_HISTORY_ACTION_LABELS}
              actionIcons={PRODUCT_HISTORY_ACTION_ICONS}
            />
          </div>
        </>
      )}
    </div>
  )
}
