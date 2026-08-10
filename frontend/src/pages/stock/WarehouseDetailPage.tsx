import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { listStock, listWarehouses, setWarehouseAssignments, type StockItem, type Warehouse } from '../../entities/inventory/api'
import { listProducts, type Product } from '../../entities/product/api'
import { listEmployees } from '../../entities/profile/api'
import type { User } from '../../entities/auth/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { Modal } from '../../shared/ui/Modal'
import { Icon } from '../../shared/ui/icons/Icon'
import { Button } from '../../shared/ui/Button'
import { formatQuantity } from '../../shared/lib/format'
import {
  AssignedUsersField,
  MODE_LABELS,
  MovementForm,
  useWarehouseManagerCandidates,
  type MovementMode,
} from './shared'

export function WarehouseDetailPage() {
  const { id } = useParams<{ id: string }>()
  const warehouseId = Number(id)
  const { user } = useAuth()
  const canManageWarehouses = user?.role === 'owner' || user?.role === 'manager'

  const [warehouse, setWarehouse] = useState<Warehouse | null>(null)
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [stock, setStock] = useState<StockItem[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [employees, setEmployees] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<MovementMode | null>(null)
  const [showAssignments, setShowAssignments] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [s, w, p, emp] = await Promise.all([
        listStock(),
        listWarehouses(),
        listProducts(),
        canManageWarehouses ? listEmployees() : Promise.resolve<User[]>([]),
      ])
      setStock(s.filter((item) => item.warehouse_id === warehouseId))
      setWarehouses(w)
      setWarehouse(w.find((item) => item.id === warehouseId) ?? null)
      setProducts(p)
      setEmployees(emp)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить остатки')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [warehouseId])

  const productName = (pid: number) => products.find((p) => p.id === pid)?.name ?? `#${pid}`
  const employeeName = (uid: number) =>
    uid === user?.id ? `${user.name} (вы)` : employees.find((e) => e.id === uid)?.name ?? `#${uid}`

  if (!loading && !warehouse) {
    return (
      <div className="stack">
        <Link to="/stock" className="back-link">
          <Icon name="chevronLeft" size={16} /> Все склады
        </Link>
        <p className="error">Склад не найден</p>
      </div>
    )
  }

  return (
    <div className="stack">
      <Link to="/stock" className="back-link">
        <Icon name="chevronLeft" size={16} /> Все склады
      </Link>

      <div className="section-title">
        <div className="stack" style={{ gap: 2 }}>
          <h2>{warehouse?.name}</h2>
          {warehouse?.address && <span className="text-muted">{warehouse.address}</span>}
        </div>
        <div className="row wrap">
          {(Object.keys(MODE_LABELS) as MovementMode[]).map((m) => (
            <Button key={m} variant="secondary" onClick={() => setMode(m)}>
              {MODE_LABELS[m]}
            </Button>
          ))}
        </div>
      </div>

      <div className="card card-full stack">
        <div className="row between">
          <span className="field-label">Ответственные</span>
          {canManageWarehouses && (
            <Button variant="secondary" onClick={() => setShowAssignments(true)}>
              Изменить
            </Button>
          )}
        </div>
        {warehouse && warehouse.assigned_user_ids.length === 0 ? (
          <p className="text-muted">Никто не назначен — доступ есть только у владельца/управляющего</p>
        ) : (
          <div className="row wrap">
            {warehouse?.assigned_user_ids.map((uid) => (
              <span key={uid} className="badge accent">
                {employeeName(uid)}
              </span>
            ))}
          </div>
        )}
      </div>

      {mode && warehouse && (
        <Modal title={`${MODE_LABELS[mode]} · ${warehouse.name}`} onClose={() => setMode(null)}>
          <MovementForm
            mode={mode}
            products={products}
            warehouses={warehouses}
            fixedWarehouseId={warehouse.id}
            onDone={() => {
              setMode(null)
              load()
            }}
          />
        </Modal>
      )}

      {showAssignments && warehouse && (
        <Modal title={`Ответственные · ${warehouse.name}`} onClose={() => setShowAssignments(false)}>
          <WarehouseAssignmentsForm
            warehouse={warehouse}
            onDone={() => {
              setShowAssignments(false)
              load()
            }}
          />
        </Modal>
      )}

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : stock.length === 0 ? (
        <p className="text-muted">На этом складе остатков пока нет</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Товар</th>
                <th>Остаток</th>
              </tr>
            </thead>
            <tbody>
              {stock.map((item, i) => (
                <tr key={i}>
                  <td>{productName(item.product_id)}</td>
                  <td>{formatQuantity(item.quantity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function WarehouseAssignmentsForm({
  warehouse,
  onDone,
}: {
  warehouse: Warehouse
  onDone: () => void
}) {
  const [selectedIds, setSelectedIds] = useState<number[]>(warehouse.assigned_user_ids)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const candidates = useWarehouseManagerCandidates()

  async function handleSubmit() {
    setError(null)
    setSaving(true)
    try {
      await setWarehouseAssignments(warehouse.id, selectedIds)
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить ответственных')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="form">
      <AssignedUsersField candidates={candidates} selectedIds={selectedIds} onChange={setSelectedIds} />
      {error && <p className="error">{error}</p>}
      <Button disabled={saving} onClick={handleSubmit}>
        {saving ? 'Сохранение…' : 'Сохранить'}
      </Button>
    </div>
  )
}
