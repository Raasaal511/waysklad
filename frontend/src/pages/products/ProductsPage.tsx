import { lazy, Suspense, useEffect, useState, type FormEvent } from 'react'
import { listProducts, createProduct, updateProduct, listUnits, type Product, type Unit } from '../../entities/product/api'
import { ApiError } from '../../shared/api/client'
import { Modal } from '../../shared/ui/Modal'
import { Icon } from '../../shared/ui/icons/Icon'
import { Button } from '../../shared/ui/Button'
import { Select } from '../../shared/ui/Select'
import { isBarcodeScannerSupported } from '../../entities/barcode/barcodeSupport'
import { normalizeDecimalInput } from '../../shared/lib/format'

const BarcodeScanner = lazy(() =>
  import('../../entities/barcode/BarcodeScanner').then((m) => ({ default: m.BarcodeScanner })),
)

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
    setShowForm(true)
  }

  function openEdit(product: Product) {
    setEditing(product)
    setShowForm(true)
  }

  function closeForm() {
    setShowForm(false)
    setEditing(null)
  }

  return (
    <div className="stack">
      <div className="section-title">
        <h2>Товары</h2>
        <Button onClick={openCreate}>
          <Icon name="plus" size={16} /> Товар
        </Button>
      </div>

      {showForm && (
        <Modal title={editing ? `Товар: ${editing.name}` : 'Новый товар'} onClose={closeForm}>
          <ProductForm
            product={editing}
            onDone={() => {
              closeForm()
              load(query)
            }}
          />
        </Modal>
      )}

      <form className="row" onSubmit={handleSearch}>
        <input
          placeholder="Поиск по названию, артикулу…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ flex: 1 }}
        />
        <Button type="submit" variant="secondary">
          Найти
        </Button>
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
}: {
  product: Product | null
  onDone: () => void
}) {
  const [name, setName] = useState(product?.name ?? '')
  const [sku, setSku] = useState(product?.sku ?? '')
  const [barcode, setBarcode] = useState(product?.barcode ?? '')
  const [showScanner, setShowScanner] = useState(false)
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
        barcode: barcode || null,
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
    <form className="form" onSubmit={handleSubmit}>
      <label className="field">
        Название
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label className="field">
        Артикул
        <input value={sku} onChange={(e) => setSku(e.target.value)} />
      </label>
      <label className="field">
        Штрихкод
        <div className="row">
          <input
            value={barcode ?? ''}
            onChange={(e) => setBarcode(e.target.value)}
            placeholder="Отсканируйте или введите вручную"
            style={{ flex: 1 }}
          />
          {isBarcodeScannerSupported() && (
            <Button variant="secondary" onClick={() => setShowScanner(true)}>
              <Icon name="barcode" size={16} />
            </Button>
          )}
        </div>
      </label>
      {showScanner && (
        <Modal title="Сканировать штрихкод" onClose={() => setShowScanner(false)}>
          <Suspense fallback={<p className="text-muted">Загрузка сканера…</p>}>
            <BarcodeScanner
              onDetected={(code) => {
                setBarcode(code)
                setShowScanner(false)
              }}
              onClose={() => setShowScanner(false)}
            />
          </Suspense>
        </Modal>
      )}
      <label className="field">
        Единица измерения
        <Select
          value={unitCode}
          onChange={setUnitCode}
          options={
            units.length === 0
              ? [{ value: unitCode, label: unitCode }]
              : units.map((u) => ({ value: u.code, label: u.name }))
          }
        />
      </label>
      <div className="row">
        <label className="field" style={{ flex: 1 }}>
          Закупочная цена
          <input
            type="text"
            inputMode="decimal"
            value={purchasePrice}
            onChange={(e) => {
              const normalized = normalizeDecimalInput(e.target.value)
              if (normalized !== null) setPurchasePrice(normalized)
            }}
          />
        </label>
        <label className="field" style={{ flex: 1 }}>
          Розничная цена
          <input
            type="text"
            inputMode="decimal"
            value={retailPrice}
            onChange={(e) => {
              const normalized = normalizeDecimalInput(e.target.value)
              if (normalized !== null) setRetailPrice(normalized)
            }}
          />
        </label>
      </div>
      <label className="field">
        Минимальный остаток
        <input
          type="text"
          inputMode="decimal"
          value={minStock}
          onChange={(e) => {
            const normalized = normalizeDecimalInput(e.target.value)
            if (normalized !== null) setMinStock(normalized)
          }}
        />
      </label>
      {error && <p className="error">{error}</p>}
      <Button type="submit" disabled={saving}>
        {saving ? 'Сохранение…' : product ? 'Сохранить изменения' : 'Создать товар'}
      </Button>
    </form>
  )
}
