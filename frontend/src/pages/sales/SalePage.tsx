import { useEffect, useState } from 'react'
import { listProducts, type Product } from '../../api/products'
import { listWarehouses, type Warehouse } from '../../api/inventory'
import { createSale, type PaymentMethod, type SaleItemInput, type Sale } from '../../api/sales'
import { ApiError } from '../../api/client'

interface CartLine {
  product: Product
  quantity: string
  price: string
}

const PAYMENT_LABELS: Record<PaymentMethod, string> = {
  cash: 'Наличные',
  transfer: 'Перевод',
  credit: 'В долг',
}

export function SalePage() {
  const [products, setProducts] = useState<Product[]>([])
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [warehouseId, setWarehouseId] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [cart, setCart] = useState<CartLine[]>([])
  const [payment, setPayment] = useState<PaymentMethod>('cash')
  const [discount, setDiscount] = useState('0')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [lastSale, setLastSale] = useState<Sale | null>(null)

  useEffect(() => {
    listProducts().then(setProducts).catch(() => {})
    listWarehouses().then((list) => {
      setWarehouses(list)
      if (list.length > 0) setWarehouseId(list[0].id)
    }).catch(() => {})
  }, [])

  const filtered = query
    ? products.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()))
    : products

  function addToCart(product: Product) {
    setCart((prev) => {
      const existing = prev.find((l) => l.product.id === product.id)
      if (existing) {
        return prev.map((l) =>
          l.product.id === product.id ? { ...l, quantity: String(Number(l.quantity) + 1) } : l,
        )
      }
      return [...prev, { product, quantity: '1', price: product.retail_price }]
    })
  }

  function updateLine(productId: number, field: 'quantity' | 'price', value: string) {
    setCart((prev) =>
      prev.map((l) => (l.product.id === productId ? { ...l, [field]: value } : l)),
    )
  }

  function removeLine(productId: number) {
    setCart((prev) => prev.filter((l) => l.product.id !== productId))
  }

  const subtotal = cart.reduce((sum, l) => sum + Number(l.quantity || 0) * Number(l.price || 0), 0)
  const total = Math.max(0, subtotal - Number(discount || 0))

  async function handleCheckout() {
    if (!warehouseId || cart.length === 0) return
    setError(null)
    setSaving(true)
    try {
      const items: SaleItemInput[] = cart.map((l) => ({
        product_id: l.product.id,
        quantity: l.quantity,
        price: l.price,
      }))
      const sale = await createSale({
        warehouse_id: warehouseId,
        payment_method: payment,
        items,
        discount,
      })
      setLastSale(sale)
      setCart([])
      setDiscount('0')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось провести продажу')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="stack">
      <h2>Продажа</h2>

      {warehouses.length > 1 && (
        <label className="field">
          Склад
          <select
            value={warehouseId ?? ''}
            onChange={(e) => setWarehouseId(Number(e.target.value))}
          >
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <input
        placeholder="Найти товар…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      <div className="table-wrap" style={{ maxHeight: 220, overflowY: 'auto' }}>
        <table>
          <tbody>
            {filtered.map((p) => (
              <tr key={p.id} onClick={() => addToCart(p)} style={{ cursor: 'pointer' }}>
                <td>{p.name}</td>
                <td>{p.retail_price} ₽</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td className="text-muted">Ничего не найдено</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {cart.length > 0 && (
        <div className="stack card card-full">
          <h3>Чек</h3>
          {cart.map((line) => (
            <div className="line-item" key={line.product.id}>
              <span>{line.product.name}</span>
              <input
                type="number"
                step="0.001"
                value={line.quantity}
                onChange={(e) => updateLine(line.product.id, 'quantity', e.target.value)}
              />
              <input
                type="number"
                step="0.01"
                value={line.price}
                onChange={(e) => updateLine(line.product.id, 'price', e.target.value)}
              />
              <button
                type="button"
                className="icon-button"
                onClick={() => removeLine(line.product.id)}
              >
                ✕
              </button>
            </div>
          ))}

          <label className="field">
            Скидка, ₽
            <input
              type="number"
              step="0.01"
              value={discount}
              onChange={(e) => setDiscount(e.target.value)}
            />
          </label>

          <label className="field">
            Оплата
            <select value={payment} onChange={(e) => setPayment(e.target.value as PaymentMethod)}>
              {Object.entries(PAYMENT_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>

          <div className="row between">
            <span className="text-muted">Итого</span>
            <strong>{total.toFixed(2)} ₽</strong>
          </div>

          {error && <p className="error">{error}</p>}

          <button type="button" onClick={handleCheckout} disabled={saving || !warehouseId}>
            {saving ? 'Проведение…' : 'Провести продажу'}
          </button>
        </div>
      )}

      {lastSale && (
        <div className="card card-full">
          <p>
            Продажа №{lastSale.id} на сумму <strong>{lastSale.total} ₽</strong> проведена
          </p>
        </div>
      )}
    </div>
  )
}
