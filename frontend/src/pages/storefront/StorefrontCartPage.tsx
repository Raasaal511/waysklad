import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { IconTrash } from '@tabler/icons-react'
import {
  clearCustomerToken,
  loadCustomerToken,
} from '../../entities/auth/customerApi'
import {
  createStorefrontRequest,
  saveRequestToken,
} from '../../entities/storefront/api'
import { ApiError } from '../../shared/api/client'
import { formatMoney, normalizeDecimalInput } from '../../shared/lib/format'
import { Button } from '../../shared/ui/Button'
import { IconButton } from '../../shared/ui/IconButton'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { loadCart, saveCart, type StorefrontCartItem } from './cart'
import { CustomerLoginModal, notifyCustomerAuthChanged } from './CustomerLoginModal'
import styles from './Storefront.module.css'

export function StorefrontCartPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const [cart, setCart] = useState<StorefrontCartItem[]>(() => loadCart(slug))
  const [name, setName] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [customerToken, setCustomerToken] = useState(() => loadCustomerToken())
  const [showLogin, setShowLogin] = useState(false)
  const [pendingSubmit, setPendingSubmit] = useState(false)

  useEffect(() => {
    setCart(loadCart(slug))
  }, [slug])

  const total = useMemo(
    () => cart.reduce((sum, i) => sum + Number(i.retail_price) * Number(i.quantity), 0),
    [cart],
  )

  function updateCart(next: StorefrontCartItem[]) {
    setCart(next)
    saveCart(slug, next)
  }

  function updateQty(index: number, raw: string) {
    const n = normalizeDecimalInput(raw)
    if (n === null) return
    updateCart(cart.map((item, i) => (i === index ? { ...item, quantity: n } : item)))
  }

  function removeItem(index: number) {
    updateCart(cart.filter((_, i) => i !== index))
  }

  async function submitWithToken(token: string) {
    setError(null)
    setSaving(true)
    try {
      const created = await createStorefrontRequest(
        slug,
        {
          customer_name: name.trim(),
          note: note || undefined,
          items: cart.map((i) => ({
            product_id: i.product_id,
            quantity: i.quantity,
            variant_id: i.variant_id,
          })),
        },
        token,
      )
      saveRequestToken(slug, created.access_token)
      saveCart(slug, [])
      navigate(`/store/${slug}/request`, {
        state: { insufficientStock: created.insufficient_stock_at_request },
      })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearCustomerToken()
        notifyCustomerAuthChanged()
        setCustomerToken(null)
        setPendingSubmit(true)
        setShowLogin(true)
        setError('Сессия истекла — войдите снова')
        return
      }
      setError(err instanceof ApiError ? err.message : 'Не удалось отправить заказ')
    } finally {
      setSaving(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (cart.length === 0 || !name.trim()) return
    const token = loadCustomerToken()
    if (!token) {
      setPendingSubmit(true)
      setShowLogin(true)
      return
    }
    await submitWithToken(token)
  }

  return (
    <div className={styles.shell}>
      <main className={styles.cartPageContent}>
        <h1 className={styles.pageTitle}>Корзина</h1>

        {cart.length === 0 ? (
          <div className={styles.emptyState}>
            <p>Корзина пуста</p>
            <Link to={`/store/${slug}`}>
              <Button>В каталог</Button>
            </Link>
          </div>
        ) : (
          <>
            <div className={styles.cartList}>
              {cart.map((item, index) => (
                <div key={`${item.product_id}-${item.variant_id ?? 'x'}`} className={styles.cartRow}>
                  <ProductPhoto src={item.photo} />
                  <div className={styles.cartRowBody}>
                    <strong>{item.name}</strong>
                    {item.variant_label && <span className={styles.muted}>{item.variant_label}</span>}
                    <span>{formatMoney(item.retail_price)} ₽</span>
                    <input
                      type="text"
                      inputMode="decimal"
                      value={item.quantity}
                      onChange={(e) => updateQty(index, e.target.value)}
                      className={styles.qtyInput}
                    />
                  </div>
                  <IconButton
                    variant="danger"
                    onClick={() => removeItem(index)}
                    aria-label="Убрать"
                  >
                    <IconTrash size={16} stroke={1.8} />
                  </IconButton>
                </div>
              ))}
            </div>

            <p className={styles.cartTotal}>
              Оценка: <strong>{formatMoney(String(total))} ₽</strong>
              <span className={styles.muted}> — окончательная сумма после подтверждения магазина</span>
            </p>

            <form className={styles.checkoutForm} onSubmit={handleSubmit}>
              <h2>Оформить заказ</h2>
              <p className={styles.muted}>
                Это не мгновенный заказ — магазин подтвердит наличие и свяжется с вами.
                {!customerToken && ' Перед отправкой нужно войти через Telegram.'}
              </p>
              <label className={styles.field}>
                Ваше имя *
                <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
              </label>
              <label className={styles.field}>
                Комментарий
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={1000}
                  rows={3}
                />
              </label>
              {error && <p className={styles.error}>{error}</p>}
              <Button type="submit" disabled={saving || !name.trim()}>
                {saving
                  ? 'Отправка…'
                  : customerToken
                    ? 'Оформить заказ'
                    : 'Войти и оформить'}
              </Button>
            </form>
          </>
        )}
      </main>

      {showLogin && (
        <CustomerLoginModal
          onClose={() => {
            setShowLogin(false)
            setPendingSubmit(false)
          }}
          onSuccess={async (accessToken) => {
            setCustomerToken(accessToken)
            notifyCustomerAuthChanged()
            setShowLogin(false)
            if (pendingSubmit && name.trim() && cart.length > 0) {
              setPendingSubmit(false)
              await submitWithToken(accessToken)
            }
          }}
        />
      )}
    </div>
  )
}
