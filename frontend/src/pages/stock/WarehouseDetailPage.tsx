import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  listStock,
  listWarehouses,
  setWarehouseAssignments,
  updateWarehouseDetails,
  getRestockRecommendations,
  type StockItem,
  type Warehouse,
  type RestockRecommendation,
} from '../../entities/inventory/api'
import { listAllProducts, listCategories, listUnits, type Category, type Product, type Unit } from '../../entities/product/api'
import { listEmployees } from '../../entities/profile/api'
import type { User } from '../../entities/auth/api'
import { ApiError } from '../../shared/api/client'
import { useAuth } from '../../app/AuthContext'
import { Modal } from '../../shared/ui/Modal'
import { IconChevronLeft, IconPencil, IconTrendingUp, IconArrowBarToDown } from '@tabler/icons-react'
import { IconButton } from '../../shared/ui/IconButton'
import { Button } from '../../shared/ui/Button'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { StockWarningIcon } from '../../shared/ui/StockWarningIcon'
import { formatQuantity, isLowStock, isOutOfStock } from '../../shared/lib/format'
import {
  AssignedUsersField,
  MODE_LABELS,
  MODE_ICONS,
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
  const [allStock, setAllStock] = useState<StockItem[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [units, setUnits] = useState<Unit[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [employees, setEmployees] = useState<User[]>([])
  const [recommendations, setRecommendations] = useState<RestockRecommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<MovementMode | null>(null)
  const [restockProductId, setRestockProductId] = useState<number | null>(null)
  const [showEdit, setShowEdit] = useState(false)

  const stock = allStock.filter((item) => item.warehouse_id === warehouseId)

  async function load() {
    setLoading(true)
    try {
      const [s, w, p, u, c, emp, rec] = await Promise.all([
        listStock(),
        listWarehouses(),
        listAllProducts(),
        listUnits(),
        listCategories(),
        canManageWarehouses ? listEmployees() : Promise.resolve<User[]>([]),
        getRestockRecommendations(warehouseId),
      ])
      setAllStock(s)
      setWarehouses(w)
      setWarehouse(w.find((item) => item.id === warehouseId) ?? null)
      setProducts(p)
      setUnits(u)
      setCategories(c)
      setEmployees(emp)
      setRecommendations(rec)
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

  const productById = (pid: number) => products.find((p) => p.id === pid)
  const productName = (pid: number) => productById(pid)?.name ?? `#${pid}`
  const unitName = (code: string) => units.find((u) => u.code === code)?.name ?? code
  const employeeName = (uid: number) =>
    uid === user?.id ? `${user.name} (вы)` : employees.find((e) => e.id === uid)?.name ?? `#${uid}`

  if (!loading && !warehouse) {
    return (
      <div className="stack">
        <Link to="/stock" className="back-link">
          <IconChevronLeft size={16} stroke={1.8} /> Все склады
        </Link>
        <p className="error">Склад не найден</p>
      </div>
    )
  }

  return (
    <div className="stack">
      <Link to="/stock" className="back-link">
        <IconChevronLeft size={16} stroke={1.8} /> Все склады
      </Link>

      <div className="section-title">
        <div className="stack" style={{ gap: 2 }}>
          <div className="row" style={{ gap: 6 }}>
            <h2>{warehouse?.name}</h2>
            {canManageWarehouses && warehouse && (
              <IconButton
                variant="muted"
                tooltip="Изменить склад"
                aria-label="Изменить склад"
                onClick={() => setShowEdit(true)}
              >
                <IconPencil size={16} stroke={1.8} />
              </IconButton>
            )}
          </div>
          {warehouse?.address && <span className="text-muted">{warehouse.address}</span>}
        </div>
        <div className="row" style={{ gap: 8 }}>
          {(Object.keys(MODE_LABELS) as MovementMode[]).map((m) => {
            const Icon = MODE_ICONS[m]
            return (
              <IconButton key={m} variant="accent" size="lg" tooltip={MODE_LABELS[m]} onClick={() => setMode(m)}>
                <Icon size={22} stroke={1.8} />
              </IconButton>
            )
          })}
        </div>
      </div>

      <div className="card card-full stack">
        <span className="field-label">Ответственные</span>
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
        <Modal
          title={`${MODE_LABELS[mode]} · ${warehouse.name}`}
          onClose={() => {
            setMode(null)
            setRestockProductId(null)
          }}
          size="full"
        >
          <MovementForm
            mode={mode}
            products={products}
            warehouses={warehouses}
            units={units}
            categories={categories}
            stock={allStock}
            fixedWarehouseId={warehouse.id}
            initialProductId={restockProductId ?? undefined}
            onDone={() => {
              setMode(null)
              setRestockProductId(null)
              load()
            }}
          />
        </Modal>
      )}

      {showEdit && warehouse && (
        <Modal title={`Изменить склад · ${warehouse.name}`} onClose={() => setShowEdit(false)}>
          <WarehouseEditForm
            warehouse={warehouse}
            onDone={() => {
              setShowEdit(false)
              load()
            }}
          />
        </Modal>
      )}

      {error && <p className="error">{error}</p>}

      {!loading && recommendations.length > 0 && (
        <div className="stack">
          <div className="row" style={{ gap: 6 }}>
            <IconTrendingUp size={18} stroke={1.8} className="restock-title-icon" />
            <h3>Стоит дозаказать</h3>
          </div>
          <p className="text-muted">
            Заканчивается, но хорошо продаётся — раскупили за последний месяц, есть смысл пополнить.
          </p>
          <div className="product-grid">
            {recommendations.map((rec) => (
              <div key={rec.product_id} className="card restock-tile">
                <Link to={`/products?open=${rec.product_id}`} className="restock-tile-name">
                  {rec.product_name}
                </Link>
                <div className="row wrap" style={{ gap: 6 }}>
                  <span className="badge warning">
                    Остаток: {formatQuantity(rec.quantity)} {unitName(productById(rec.product_id)?.unit_code ?? 'pcs')}
                  </span>
                  <span className="badge accent">
                    Продано за 30 дн.: {formatQuantity(rec.quantity_sold)}
                  </span>
                </div>
                <Button
                  variant="secondary"
                  onClick={() => {
                    setRestockProductId(rec.product_id)
                    setMode('receive')
                  }}
                >
                  <IconArrowBarToDown size={16} stroke={1.8} /> Дозаказать
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : stock.length === 0 ? (
        <p className="text-muted">На этом складе остатков пока нет</p>
      ) : (
        <div className="stack">
          <h3>Товары на складе</h3>
          <div className="product-grid">
            {stock.map((item, i) => {
              const product = productById(item.product_id)
              const out = isOutOfStock(item.quantity)
              const low = product != null && isLowStock(item.quantity, product.min_stock)
              return (
                <Link
                  key={i}
                  to={`/products?open=${item.product_id}`}
                  className="product-tile"
                >
                  <ProductPhoto src={product?.photo ?? ''} />
                  <span className="product-tile-name">{productName(item.product_id)}</span>
                  <span
                    className={`product-tile-stock${out ? ' product-tile-stock-out' : ' product-tile-stock-in'}`}
                  >
                    <span className="product-tile-stock-label">Остаток:</span>
                    <span className="product-tile-stock-value">
                      {formatQuantity(item.quantity)} {unitName(product?.unit_code ?? 'pcs')}
                    </span>
                    {low && <StockWarningIcon />}
                  </span>
                </Link>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function WarehouseEditForm({
  warehouse,
  onDone,
}: {
  warehouse: Warehouse
  onDone: () => void
}) {
  const [name, setName] = useState(warehouse.name)
  const [address, setAddress] = useState(warehouse.address)
  const [selectedIds, setSelectedIds] = useState<number[]>(warehouse.assigned_user_ids)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const candidates = useWarehouseManagerCandidates()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await updateWarehouseDetails(warehouse.id, { name, address })
      await setWarehouseAssignments(warehouse.id, selectedIds)
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить склад')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <label className="field">
        Название
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className="field">
        Адрес
        <input value={address} onChange={(e) => setAddress(e.target.value)} />
      </label>
      <label className="field">
        Ответственные
        <AssignedUsersField candidates={candidates} selectedIds={selectedIds} onChange={setSelectedIds} />
      </label>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Сохранить'}
      </Button>
    </form>
  )
}
