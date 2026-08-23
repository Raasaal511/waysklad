import { useEffect, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { listStock, listWarehouses, type StockItem, type Warehouse } from '../../entities/inventory/api'
import { listAllProducts, type Product } from '../../entities/product/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { IconPlus, IconBuildingWarehouse, IconChevronRight, IconHistory } from '@tabler/icons-react'
import { IconButton } from '../../shared/ui/IconButton'
import { Button } from '../../shared/ui/Button'
import { isLowStock } from '../../shared/lib/format'
import { NewWarehouseForm } from './shared'
import layoutStyles from '../../shared/ui/Layout.module.css'

export function StockPage() {
  const [stock, setStock] = useState<StockItem[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showWarehouseForm, setShowWarehouseForm] = useState(false)

  async function load(silent = false) {
    if (!silent) setLoading(true)
    try {
      const [s, w, p] = await Promise.all([listStock(), listWarehouses(), listAllProducts()])
      setStock(s)
      setWarehouses(w)
      setProducts(p)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить остатки')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const minStockById = new Map(products.map((p) => [p.id, p.min_stock]))
  const itemCount = (warehouseId: number) => stock.filter((s) => s.warehouse_id === warehouseId).length
  const lowStockCount = (warehouseId: number) =>
    stock.filter(
      (s) => s.warehouse_id === warehouseId && isLowStock(s.quantity, minStockById.get(s.product_id) ?? '0'),
    ).length

  const totalPositions = stock.length
  const totalLowStock = stock.filter((s) => isLowStock(s.quantity, minStockById.get(s.product_id) ?? '0')).length

  return (
    <div className={layoutStyles.stack}>
      <div className={layoutStyles.sectionTitle}>
        <h2>Склады</h2>
        <div className={layoutStyles.row} style={{ gap: 8 }}>
          <Link to="/stock/history">
            <IconButton variant="accent" tooltip="История движения" style={{ width: 40, height: 40 }}>
              <IconHistory size={19} stroke={1.8} />
            </IconButton>
          </Link>
          <Button onClick={() => setShowWarehouseForm(true)}>
            <IconPlus size={16} stroke={1.8} /> Склад
          </Button>
        </div>
      </div>

      {showWarehouseForm && (
        <Modal title="Новый склад" onClose={() => setShowWarehouseForm(false)}>
          <NewWarehouseForm
            onCreated={() => {
              setShowWarehouseForm(false)
              load(true)
            }}
          />
        </Modal>
      )}

      {error && <p className={layoutStyles.error}>{error}</p>}

      {!loading && warehouses.length > 1 && (
        <div className={[layoutStyles.card, layoutStyles.cardFull].join(' ')}>
          <div className="grid-stats">
            <div className="stat">
              <span className="stat-label">Складов</span>
              <span className="stat-value">{warehouses.length}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Позиций на остатке</span>
              <span className="stat-value">{totalPositions}</span>
            </div>
            <div className="stat">
              <span className="stat-label">Заканчивается</span>
              <span className="stat-value">{totalLowStock}</span>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : warehouses.length === 0 ? (
        <p className={layoutStyles.textMuted}>Складов пока нет</p>
      ) : (
        <div className="warehouse-tiles">
          {warehouses.map((w, i) => {
            const low = lowStockCount(w.id)
            return (
              <Link
                key={w.id}
                to={`/stock/${w.id}`}
                className="warehouse-tile sale-history-row-in"
                style={{ '--row-delay': `${Math.min(i, 12) * 40}ms` } as CSSProperties}
              >
                <div className="warehouse-tile-header">
                  <span className="warehouse-tile-icon">
                    <IconBuildingWarehouse size={26} stroke={1.6} />
                  </span>
                  <div className="warehouse-tile-heading">
                    <strong className="warehouse-tile-name">{w.name}</strong>
                    <span className={layoutStyles.textMuted}>{w.address || 'Без адреса'}</span>
                  </div>
                  <IconChevronRight size={20} stroke={1.8} className="warehouse-tile-chevron" />
                </div>

                <div className="warehouse-tile-stats">
                  <div className="stat">
                    <span className="stat-label">Позиций</span>
                    <span className="stat-value">{itemCount(w.id)}</span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Заканчивается</span>
                    <span className={`stat-value${low > 0 ? ' stat-value-warning' : ''}`}>{low}</span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Ответственных</span>
                    <span className="stat-value">{w.assigned_user_ids.length}</span>
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
