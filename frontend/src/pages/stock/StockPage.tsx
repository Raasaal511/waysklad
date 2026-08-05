import { useEffect, useState, type FormEvent } from 'react'
import {
  listStock,
  listWarehouses,
  createWarehouse,
  receiveGoods,
  writeOff,
  transferStock,
  type StockItem,
  type Warehouse,
} from '../../api/inventory'
import { listProducts, type Product } from '../../api/products'
import { ApiError } from '../../api/client'

type MovementMode = 'receive' | 'write_off' | 'transfer'

const MODE_LABELS: Record<MovementMode, string> = {
  receive: 'Приёмка',
  write_off: 'Списание',
  transfer: 'Перемещение',
}

export function StockPage() {
  const [stock, setStock] = useState<StockItem[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<MovementMode | null>(null)
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

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Остатки</h2>
        <div className="row wrap">
          <button type="button" className="secondary" onClick={() => setShowWarehouseForm((v) => !v)}>
            + Склад
          </button>
          {(Object.keys(MODE_LABELS) as MovementMode[]).map((m) => (
            <button
              key={m}
              type="button"
              className={mode === m ? '' : 'secondary'}
              onClick={() => setMode((v) => (v === m ? null : m))}
            >
              {MODE_LABELS[m]}
            </button>
          ))}
        </div>
      </div>

      {showWarehouseForm && (
        <NewWarehouseForm
          onCreated={() => {
            setShowWarehouseForm(false)
            load()
          }}
        />
      )}

      {mode && (
        <MovementForm
          mode={mode}
          products={products}
          warehouses={warehouses}
          onDone={() => {
            setMode(null)
            load()
          }}
        />
      )}

      <div className="stack">
        <h3>Склады</h3>
        <div className="row wrap">
          {warehouses.map((w) => (
            <span key={w.id} className="badge accent">
              {w.name}
            </span>
          ))}
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : stock.length === 0 ? (
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
                  <td>{item.quantity}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function NewWarehouseForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await createWarehouse({ name, address })
      onCreated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать склад')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form card card-full" onSubmit={handleSubmit}>
      <label className="field">
        Название склада
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className="field">
        Адрес
        <input value={address} onChange={(e) => setAddress(e.target.value)} />
      </label>
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Создать склад'}
      </button>
    </form>
  )
}

function MovementForm({
  mode,
  products,
  warehouses,
  onDone,
}: {
  mode: MovementMode
  products: Product[]
  warehouses: Warehouse[]
  onDone: () => void
}) {
  const [warehouseId, setWarehouseId] = useState<number | null>(warehouses[0]?.id ?? null)
  const [toWarehouseId, setToWarehouseId] = useState<number | null>(warehouses[1]?.id ?? null)
  const [productId, setProductId] = useState<number | null>(products[0]?.id ?? null)
  const [quantity, setQuantity] = useState('')
  const [cost, setCost] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!warehouseId || !productId) return
    setError(null)
    setSaving(true)
    try {
      if (mode === 'receive') {
        await receiveGoods({
          warehouse_id: warehouseId,
          lines: [{ product_id: productId, quantity, cost: cost || undefined }],
        })
      } else if (mode === 'write_off') {
        await writeOff({ warehouse_id: warehouseId, lines: [{ product_id: productId, quantity }] })
      } else {
        if (!toWarehouseId) return
        await transferStock({
          warehouse_id: warehouseId,
          to_warehouse_id: toWarehouseId,
          lines: [{ product_id: productId, quantity }],
        })
      }
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось выполнить операцию')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form card card-full" onSubmit={handleSubmit}>
      <label className="field">
        {mode === 'transfer' ? 'Склад-отправитель' : 'Склад'}
        <select value={warehouseId ?? ''} onChange={(e) => setWarehouseId(Number(e.target.value))}>
          {warehouses.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
      </label>
      {mode === 'transfer' && (
        <label className="field">
          Склад-получатель
          <select
            value={toWarehouseId ?? ''}
            onChange={(e) => setToWarehouseId(Number(e.target.value))}
          >
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="field">
        Товар
        <select value={productId ?? ''} onChange={(e) => setProductId(Number(e.target.value))}>
          {products.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <div className="row">
        <label className="field" style={{ flex: 1 }}>
          Количество
          <input
            type="number"
            step="0.001"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            required
          />
        </label>
        {mode === 'receive' && (
          <label className="field" style={{ flex: 1 }}>
            Закупочная цена
            <input type="number" step="0.01" value={cost} onChange={(e) => setCost(e.target.value)} />
          </label>
        )}
      </div>
      {error && <p className="error">{error}</p>}
      <button
        type="submit"
        disabled={saving || !warehouseId || !productId || (mode === 'transfer' && !toWarehouseId)}
      >
        {saving ? 'Проведение…' : `Провести: ${MODE_LABELS[mode]}`}
      </button>
    </form>
  )
}
