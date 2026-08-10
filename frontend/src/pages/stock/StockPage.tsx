import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listStock, listWarehouses, type StockItem, type Warehouse } from '../../entities/inventory/api'
import { listProducts, type Product } from '../../entities/product/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { Icon } from '../../shared/ui/icons/Icon'
import { Button } from '../../shared/ui/Button'
import { formatQuantity } from '../../shared/lib/format'
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
      const [s, w, p] = await Promise.all([listStock(), listWarehouses(), listProducts()])
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

  const productName = (id: number) => products.find((p) => p.id === id)?.name ?? `#${id}`
  const warehouseName = (id: number) => warehouses.find((w) => w.id === id)?.name ?? `#${id}`
  const itemCount = (warehouseId: number) => stock.filter((s) => s.warehouse_id === warehouseId).length

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Остатки</h2>
        <Button onClick={() => setShowWarehouseForm(true)}>
          <Icon name="plus" size={16} /> Склад
        </Button>
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
      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : warehouses.length === 0 ? (
        <p className="text-muted">Складов пока нет</p>
      ) : (
        <div className="warehouse-grid">
          {warehouses.map((w) => (
            <Link key={w.id} to={`/stock/${w.id}`} className="card warehouse-card">
              <div className="row between">
                <div className="row" style={{ gap: 10 }}>
                  <span className="warehouse-card-icon">
                    <Icon name="stock" size={18} />
                  </span>
                  <strong>{w.name}</strong>
                </div>
                <span className="warehouse-card-chevron">
                  <Icon name="chevronRight" size={16} />
                </span>
              </div>
              {w.address && <span className="text-muted">{w.address}</span>}
              <div className="row wrap" style={{ gap: 6 }}>
                <span className="badge accent">{itemCount(w.id)} позиций</span>
                <span className="badge">
                  {w.assigned_user_ids.length === 0
                    ? 'Без ответственных'
                    : `Ответственных: ${w.assigned_user_ids.length}`}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {!loading && (
        <div className="stack">
          <h3>Все товары по складам</h3>
          {stock.length === 0 ? (
            <p className="text-muted">Остатков пока нет</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Товар</th>
                    <th>Склад</th>
                    <th>Остаток</th>
                  </tr>
                </thead>
                <tbody>
                  {stock.map((item, i) => (
                    <tr key={i}>
                      <td>{productName(item.product_id)}</td>
                      <td>{warehouseName(item.warehouse_id)}</td>
                      <td>{formatQuantity(item.quantity)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
