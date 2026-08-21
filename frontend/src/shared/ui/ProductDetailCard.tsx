import { useState, type CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  getProductHistory,
  type Product,
  type Unit,
  type Category,
  type ProductHistoryEntry,
} from '../../entities/product/api'
import type { Warehouse, StockItem } from '../../entities/inventory/api'
import { Modal } from './Modal'
import { IconButton } from './IconButton'
import { InfoHint } from './InfoHint'
import { formatMoney, formatQuantity } from '../lib/format'
import {
  IconPencil,
  IconCheck,
  IconPhoto,
  IconChevronDown,
  IconChevronRight,
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

const STOCK_BY_WAREHOUSE_COLUMNS = '2fr 1fr 16px'
const VARIANTS_COLUMNS = '1fr 1fr 1.4fr'

export function ProductDetailCard({
  product,
  categories,
  units,
  warehouses,
  stock,
  onClose,
  onEdit,
}: {
  product: Product
  categories: Category[]
  units: Unit[]
  warehouses: Warehouse[]
  stock: StockItem[]
  onClose: () => void
  onEdit?: () => void
}) {
  const navigate = useNavigate()
  const [history, setHistory] = useState<ProductHistoryEntry[] | null>(null)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)

  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code
  const categoryName = (id: number | null) =>
    id == null ? null : categories.find((c) => c.id === id)?.name ?? `#${id}`

  const stockByWarehouse = warehouses
    .map((w) => {
      const rows = stock.filter((s) => s.product_id === product.id && s.warehouse_id === w.id)
      return {
        warehouse: w,
        quantity: rows.reduce((sum, s) => sum + Number(s.quantity), 0),
        reserved: rows.reduce((sum, s) => sum + Number(s.reserved), 0),
      }
    })
    .filter((row) => row.quantity > 0 || warehouses.length <= 5)

  async function toggleHistory() {
    if (historyOpen) {
      setHistoryOpen(false)
      return
    }
    setHistoryOpen(true)
    if (history !== null) return
    setLoadingHistory(true)
    try {
      setHistory(await getProductHistory(product.id))
    } catch {
      setHistory([])
    } finally {
      setLoadingHistory(false)
    }
  }

  return (
    <Modal title={product.name} onClose={onClose} size="full">
      <div className="stack">
        <div className="product-detail-header">
          {product.photo ? (
            <img src={product.photo} alt="" className="product-detail-photo" />
          ) : (
            <div className="product-detail-photo product-detail-photo-empty">
              <IconPhoto size={40} stroke={1.5} />
            </div>
          )}
          <div className="product-detail-header-info">
            <div className="row between">
              <h3 className="product-detail-title">{product.name}</h3>
              {onEdit && (
                <div className="sale-detail-actions">
                  <IconButton
                    variant="muted"
                    size="lg"
                    onClick={onEdit}
                    tooltip="Редактировать товар"
                    aria-label="Редактировать товар"
                  >
                    <IconPencil size={22} stroke={1.8} />
                  </IconButton>
                </div>
              )}
            </div>
            <div className="product-detail-header-tags">
              {categoryName(product.category_id) && (
                <span className="badge accent">{categoryName(product.category_id)}</span>
              )}
              {product.sku && <span className="product-detail-sku">Артикул {product.sku}</span>}
            </div>
            <span className="product-detail-price">{formatMoney(product.retail_price)} ₽</span>
          </div>
        </div>

        <div className="sale-detail-meta">
          <div className="sale-detail-meta-item">
            <span className="text-muted">Штрихкод</span>
            <span>{product.barcode || '—'}</span>
          </div>
          <div className="sale-detail-meta-item">
            <span className="text-muted">Единица измерения</span>
            <span>{unitName(product.unit_code)}</span>
          </div>
          {product.purchase_price !== null && (
            <div className="sale-detail-meta-item">
              <span className="text-muted">Закупочная цена</span>
              <span>{formatMoney(product.purchase_price)} ₽</span>
            </div>
          )}
          {product.margin !== null && (
            <div className="sale-detail-meta-item">
              <span className="text-muted">Маржа</span>
              <span>{formatMoney(product.margin)} ₽</span>
            </div>
          )}
          <div className="sale-detail-meta-item">
            <span className="text-muted">Минимальный остаток</span>
            <span>
              {formatQuantity(product.min_stock)} {unitName(product.unit_code)}
            </span>
          </div>
        </div>

        <h3 className="sale-detail-section-title">Остатки по складам</h3>
        {stockByWarehouse.length === 0 ? (
          <p className="text-muted">Остатков нет</p>
        ) : (
          <div className="data-table">
            <div className="data-table-head" style={{ gridTemplateColumns: STOCK_BY_WAREHOUSE_COLUMNS }}>
              <span>Склад</span>
              <span>Остаток</span>
            </div>
            <div className="data-table-body">
              {stockByWarehouse.map((row, i) => (
                <button
                  key={row.warehouse.id}
                  type="button"
                  className="data-row data-row-link sale-history-row-in"
                  style={
                    {
                      gridTemplateColumns: STOCK_BY_WAREHOUSE_COLUMNS,
                      '--row-delay': `${Math.min(i, 12) * 25}ms`,
                    } as CSSProperties
                  }
                  onClick={() => {
                    onClose()
                    navigate(`/stock/${row.warehouse.id}`)
                  }}
                >
                  <span className="data-row-name">{row.warehouse.name}</span>
                  <span>
                    {row.quantity === 0 ? (
                      <span className="text-muted">Нет в наличии</span>
                    ) : (
                      <>
                        {formatQuantity(String(row.quantity))} {unitName(product.unit_code)}
                      </>
                    )}
                    {row.reserved > 0 && (
                      <span className="text-muted">
                        {' '}
                        (резерв {formatQuantity(String(row.reserved))})
                        <InfoHint text="Зарезервировано под заказы клиентов и недоступно для продажи — освободится, когда заказ выдадут или отменят." />
                      </span>
                    )}
                  </span>
                  <IconChevronRight size={14} stroke={1.8} className="data-row-chevron" />
                </button>
              ))}
            </div>
          </div>
        )}

        {product.variants.length > 0 && (
          <>
            <h3 className="sale-detail-section-title">Варианты</h3>
            <div className="data-table">
              <div className="data-table-head" style={{ gridTemplateColumns: VARIANTS_COLUMNS }}>
                <span>Размер</span>
                <span>Цвет</span>
                <span>Штрихкод</span>
              </div>
              <div className="data-table-body">
                {product.variants.map((v, i) => (
                  <div
                    key={v.id}
                    className="data-row sale-history-row-in"
                    style={
                      {
                        gridTemplateColumns: VARIANTS_COLUMNS,
                        '--row-delay': `${Math.min(i, 12) * 25}ms`,
                      } as CSSProperties
                    }
                  >
                    <span>{v.size || '—'}</span>
                    <span>{v.color || '—'}</span>
                    <span className="text-muted">{v.barcode || '—'}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        <div className="sale-detail-history">
          <button
            type="button"
            className="disclosure-link"
            onClick={toggleHistory}
            disabled={loadingHistory}
            aria-expanded={historyOpen}
          >
            {loadingHistory ? 'Загрузка…' : 'История изменений'}
            <IconChevronDown size={14} stroke={1.8} />
          </button>
          {historyOpen &&
            (history === null ? null : history.length === 0 ? (
              <p className="text-muted">Изменений не было</p>
            ) : (
              <div className="sale-detail-history-list">
                {history.map((entry) => {
                  const HistoryIcon = PRODUCT_HISTORY_ACTION_ICONS[entry.action] ?? IconPencil
                  return (
                    <div key={entry.id} className="sale-detail-history-item">
                      <span className="sale-detail-history-icon">
                        <HistoryIcon size={15} stroke={1.8} />
                      </span>
                      <span className="sale-detail-history-label">
                        {PRODUCT_HISTORY_ACTION_LABELS[entry.action] ?? entry.action}
                      </span>
                      <span className="sale-detail-history-time">
                        {new Date(entry.created_at).toLocaleString('ru-RU', {
                          day: 'numeric',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                  )
                })}
              </div>
            ))}
        </div>
      </div>
    </Modal>
  )
}
