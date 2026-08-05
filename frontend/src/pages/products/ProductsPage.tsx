import { useEffect, useState, type FormEvent } from 'react'
import { listProducts, createProduct, type Product } from '../../api/products'
import { ApiError } from '../../api/client'

export function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)

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

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Товары</h2>
        <button type="button" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Отмена' : '+ Товар'}
        </button>
      </div>

      {showForm && (
        <NewProductForm
          onCreated={() => {
            setShowForm(false)
            load(query)
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
                <tr key={p.id}>
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

function NewProductForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState('')
  const [sku, setSku] = useState('')
  const [purchasePrice, setPurchasePrice] = useState('')
  const [retailPrice, setRetailPrice] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await createProduct({
        name,
        sku,
        purchase_price: purchasePrice || '0',
        retail_price: retailPrice || '0',
      })
      onCreated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось создать товар')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="form card card-full" onSubmit={handleSubmit}>
      <label className="field">
        Название
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className="field">
        Артикул
        <input value={sku} onChange={(e) => setSku(e.target.value)} />
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
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : 'Создать товар'}
      </button>
    </form>
  )
}
