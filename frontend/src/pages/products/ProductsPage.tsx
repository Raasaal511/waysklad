import { useEffect, useState, type FormEvent } from 'react'
import { listProducts, createProduct, updateProduct, listUnits, type Product, type Unit } from '../../api/products'
import { ApiError } from '../../api/client'

export function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Product | null>(null)

  async function load(q = '') {
    setLoading(true)
    try {
      setProducts(await listProducts(q))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить товары')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  function handleSearch(e: FormEvent) {
    e.preventDefault()
    load(query)
  }

  function openCreate() {
    setEditing(null)
    setShowForm((v) => !v)
  }

  function openEdit(product: Product) {
    setEditing(product)
    setShowForm(true)
  }

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Товары</h2>
        <button type="button" onClick={openCreate}>
          {showForm && !editing ? 'Отмена' : '+ Товар'}
        </button>
      </div>

      {showForm && (
        <ProductForm
          product={editing}
          onDone={() => {
            setShowForm(false)
            setEditing(null)
            load(query)
          }}
          onCancel={() => {
            setShowForm(false)
            setEditing(null)
          }}
        />
      )}

      <form className="row" onSubmit={handleSearch}>
        <input
          placeholder="Поиск по названию, артикулу…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ flex: 1 }}
        />
        <button type="submit" className="secondary">
          Найти
        </button>
      </form>

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p className="text-muted">Загрузка…</p>
      ) : products.length === 0 ? (
        <p className="text-muted">Товаров пока нет</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Название</th>
                <th>Артикул</th>
                <th>Ед.</th>
                <th>Закупка</th>
                <th>Розница</th>
                <th>Маржа</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id} onClick={() => openEdit(p)} style={{ cursor: 'pointer' }}>
                  <td>{p.name}</td>
                  <td>{p.sku || '—'}</td>
                  <td>{p.unit_code}</td>
                  <td>{p.purchase_price ?? '—'}</td>
                  <td>{p.retail_price}</td>
                  <td>{p.margin ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function ProductForm({
  product,
  onDone,
  onCancel,
}: {
  product: Product | null
  onDone: () => void
  onCancel: () => void
}) {
  const [name, setName] = useState(product?.name ?? '')
  const [sku, setSku] = useState(product?.sku ?? '')
  const [unitCode, setUnitCode] = useState(product?.unit_code ?? 'pcs')
  const [units, setUnits] = useState<Unit[]>([])
  const [purchasePrice, setPurchasePrice] = useState(product?.purchase_price ?? '')
  const [retailPrice, setRetailPrice] = useState(product?.retail_price ?? '')
  const [minStock, setMinStock] = useState(product?.min_stock ?? '')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    listUnits().then(setUnits).catch(() => {})
  }, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const payload = {
        name,
        sku,
        unit_code: unitCode,
        purchase_price: purchasePrice || '0',
        retail_price: retailPrice || '0',
        min_stock: minStock || '0',
      }
      if (product) {
        await updateProduct(product.id, payload)
      } else {
        await createProduct(payload)
      }
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить товар')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form card card-full" onSubmit={handleSubmit}>
      <div className="row between">
        <h3>{product ? `Товар: ${product.name}` : 'Новый товар'}</h3>
        {product && (
          <button type="button" className="secondary" onClick={onCancel}>
            Отмена
          </button>
        )}
      </div>
      <label className="field">
        Название
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className="field">
        Артикул
        <input value={sku} onChange={(e) => setSku(e.target.value)} />
      </label>
      <label className="field">
        Единица измерения
        <select value={unitCode} onChange={(e) => setUnitCode(e.target.value)}>
          {units.length === 0 ? (
            <option value={unitCode}>{unitCode}</option>
          ) : (
            units.map((u) => (
              <option key={u.code} value={u.code}>
                {u.name}
              </option>
            ))
          )}
        </select>
      </label>
      <div className="row">
        <label className="field" style={{ flex: 1 }}>
          Закупочная цена
          <input
            type="number"
            step="0.01"
            value={purchasePrice}
            onChange={(e) => setPurchasePrice(e.target.value)}
          />
        </label>
        <label className="field" style={{ flex: 1 }}>
          Розничная цена
          <input
            type="number"
            step="0.01"
            value={retailPrice}
            onChange={(e) => setRetailPrice(e.target.value)}
          />
        </label>
      </div>
      <label className="field">
        Минимальный остаток
        <input
          type="number"
          step="0.001"
          value={minStock}
          onChange={(e) => setMinStock(e.target.value)}
        />
      </label>
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : product ? 'Сохранить изменения' : 'Создать товар'}
      </button>
    </form>
  )
}
