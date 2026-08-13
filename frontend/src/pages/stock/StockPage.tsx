import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listStock, listWarehouses, type StockItem, type Warehouse } from '../../entities/inventory/api'
import { listAllProducts, type Product } from '../../entities/product/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { IconPlus, IconBuildingWarehouse, IconChevronRight, IconHistory } from '@tabler/icons-react'
import { IconButton } from '../../shared/ui/IconButton'
import { isLowStock } from '../../shared/lib/format'
import { NewWarehouseForm } from './shared'

export function StockPage() {
  const [stock, setStock] = useState<StockItem[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showWarehouseForm, setShowWarehouseForm] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [s, w, p] = await Promise.all([listStock(), listWarehouses(), listAllProducts()])
      setStock(s)
      setWarehouses(w)
      setProducts(p)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить остатки')
    } finally {
      setLoading(false)
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
    <div className="stack">
      <div className="section-title">
        <h2>Остатки</h2>
        <div className="row" style={{ gap: 8 }}>
          <Link to="/stock/history">
            <IconButton variant="accent" size="lg" tooltip="История движения">
              <IconHistory size={22} stroke={1.8} />
            </IconButton>
          </Link>
          <IconButton
            variant="accent"
            size="lg"
            tooltip="Новый склад"
            onClick={() => setShowWarehouseForm(true)}
          >
            <IconPlus size={22} stroke={1.8} />
          </IconButton>
        </div>
      </div>

      {showWarehouseForm && (
        <Modal title="Новый склад" onClose={() => setShowWarehouseForm(false)}>
          <NewWarehouseForm
            onCreated={() => {
              setShowWarehouseForm(false)
              load()
            }}
          />
        </Modal>
      )}

      {error && <p className="error">{error}</p>}

      {!loading && warehouses.length > 1 && (
        <div className="card card-full">
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
        <p className="text-muted">Загрузка…</p>
      ) : warehouses.length === 0 ? (
        <p className="text-muted">Складов пока нет</p>
      ) : (
        <div className="warehouse-grid">
          {warehouses.map((w) => {
            const low = lowStockCount(w.id)
            return (
              <Link key={w.id} to={`/stock/${w.id}`} className="card warehouse-card">
                <div className="row between">
                  <div className="row" style={{ gap: 10 }}>
                    <span className="warehouse-card-icon">
                      <IconBuildingWarehouse size={18} stroke={1.8} />
                    </span>
                    <strong>{w.name}</strong>
                  </div>
                  <span className="warehouse-card-chevron">
                    <IconChevronRight size={16} stroke={1.8} />
                  </span>
                </div>
                {w.address && <span className="text-muted">{w.address}</span>}
                <div className="row wrap" style={{ gap: 6 }}>
                  <span className="badge accent">{itemCount(w.id)} позиций</span>
                  {low > 0 && <span className="badge warning">Заканчивается: {low}</span>}
                  <span className="badge">
                    {w.assigned_user_ids.length === 0
                      ? 'Без ответственных'
                      : `Ответственных: ${w.assigned_user_ids.length}`}
                  </span>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
