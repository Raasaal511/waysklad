import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { IconChevronDown, IconInfoCircle, IconTrash, IconUserCircle } from '@tabler/icons-react'
import {
  clearCustomerToken,
  getCustomerProfile,
  loadCustomerToken,
  savePendingCheckout,
  takePendingCheckout,
  updateCustomerProfile,
  type CustomerProfile,
} from '../../entities/auth/customerApi'
import {
  bumpOrderQty,
  createStorefrontRequest,
  getStorefrontShopProfileCached,
  peekCachedStorefrontShopProfile,
  saveRequestToken,
} from '../../entities/storefront/api'
import { ApiError } from '../../shared/api/client'
import { formatMoney, formatQuantity, normalizeDecimalInput, plural } from '../../shared/lib/format'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { Button } from '../../shared/ui/Button'
import { EmptyState } from '../../shared/ui/EmptyState'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { loadCart, saveCart, type StorefrontCartItem } from './cart'
import { notifyCustomerAuthChanged } from './customerAuthEvents'
import { QtyStepper } from './QtyStepper'
import styles from './StorefrontCartPage.module.css'

function minQty(item: StorefrontCartItem): number {
  const min = Number(item.min_order_qty)
  return Number.isFinite(min) && min > 0 ? min : 1
}

/** Как магазин увидит покупателя: имя из профиля, иначе логин, иначе телефон —
 *  то же правило, что на сервере (create_request.py), поле «Ваше имя» не нужно. */
function displayName(profile: CustomerProfile): string {
  return profile.name.trim() || profile.username.trim() || profile.phone
}

export function StorefrontCartPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const [cart, setCart] = useState<StorefrontCartItem[]>(() => loadCart(slug))
  const [note, setNote] = useState('')
  const [noteOpen, setNoteOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [customerToken, setCustomerToken] = useState(() => loadCustomerToken())
  const [profile, setProfile] = useState<CustomerProfile | null>(null)
  const [editingName, setEditingName] = useState(false)
  const [nameDraft, setNameDraft] = useState('')
  const [shopName, setShopName] = useState(() => peekCachedStorefrontShopProfile(slug)?.name ?? null)
  const errorRef = useRef<HTMLParagraphElement>(null)

  // На телефоне кнопка «Оформить» в липкой панели, а ошибка — в потоке страницы:
  // без прокрутки к ней нажатие выглядело бы так, будто ничего не произошло.
  useEffect(() => {
    if (error) errorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [error])

  useEffect(() => {
    setCart(loadCart(slug))
  }, [slug])

  useEffect(() => {
    function syncAuth() {
      setCustomerToken(loadCustomerToken())
    }
    window.addEventListener('waysklad:customer-auth', syncAuth)
    window.addEventListener('storage', syncAuth)
    return () => {
      window.removeEventListener('waysklad:customer-auth', syncAuth)
      window.removeEventListener('storage', syncAuth)
    }
  }, [])

  useEffect(() => {
    if (!customerToken) {
      setProfile(null)
      return
    }
    let cancelled = false
    getCustomerProfile()
      .then((p) => {
        if (!cancelled) setProfile(p)
      })
      .catch(() => {
        if (!cancelled) setProfile(null)
      })
    return () => {
      cancelled = true
    }
  }, [customerToken])

  // Вернулись со входа — отправляем заказ сразу, второй раз жать «Оформить» не нужно.
  useEffect(() => {
    const pending = takePendingCheckout(slug)
    if (!pending) return
    setNote(pending.note)
    if (pending.note) setNoteOpen(true)
    const token = loadCustomerToken()
    if (token && loadCart(slug).length > 0) void submit(token, pending.note)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug])

  useEffect(() => {
    const cached = peekCachedStorefrontShopProfile(slug)
    if (cached) {
      setShopName(cached.name)
      return
    }
    let cancelled = false
    getStorefrontShopProfileCached(slug)
      .then((p) => {
        if (!cancelled) setShopName(p.name)
      })
      .catch(() => {
        if (!cancelled) setShopName(null)
      })
    return () => {
      cancelled = true
    }
  }, [slug])

  useEffect(() => {
    setPageMeta({ title: shopName ? `${shopName} — Корзина` : 'Корзина' })
    return () => resetPageMeta()
  }, [shopName])

  const total = useMemo(
    () => cart.reduce((sum, i) => sum + Number(i.retail_price) * Number(i.quantity || 0), 0),
    [cart],
  )
  const positions = cart.length

  function updateCart(next: StorefrontCartItem[]) {
    setCart(next)
    saveCart(slug, next)
  }

  function setQty(index: number, quantity: string) {
    updateCart(cart.map((item, i) => (i === index ? { ...item, quantity } : item)))
  }

  function stepQty(index: number, delta: 1 | -1) {
    const item = cart[index]
    // минимум и шаг товара — те же правила, что на странице товара и на сервере:
    // иначе «−» до 9 при минимуме 10 давал ошибку уже при оформлении
    setQty(index, String(bumpOrderQty(Number(item.quantity || 0), delta, item.min_order_qty, item.order_step_qty)))
  }

  function typeQty(index: number, raw: string) {
    const n = normalizeDecimalInput(raw)
    if (n === null) return
    setQty(index, n)
  }

  function removeItem(index: number) {
    updateCart(cart.filter((_, i) => i !== index))
  }

  function goLogin() {
    savePendingCheckout(slug, { name: '', note })
    const next = encodeURIComponent(`/store/${slug}/cart`)
    navigate(`/store/${slug}/login?next=${next}`)
  }

  /** Пустое или нулевое количество (стёрли цифру в поле) — сказать, а не выкинуть
   *  строку молча: корзина после отправки очищается, и товар бы потерялся. */
  function quantityProblem(items: StorefrontCartItem[]): string | null {
    for (const item of items) {
      const qty = Number(item.quantity)
      if (!Number.isFinite(qty) || qty <= 0) return `Укажите количество для «${item.name}»`
      const min = minQty(item)
      if (qty < min) return `«${item.name}»: минимум ${formatQuantity(min)}`
    }
    return null
  }

  async function submit(token: string, noteText: string) {
    const items = loadCart(slug)
    const problem = quantityProblem(items)
    if (problem) {
      setError(problem)
      return
    }
    setError(null)
    setSaving(true)
    try {
      const created = await createStorefrontRequest(
        slug,
        {
          note: noteText.trim() || undefined,
          items: items.map((i) => ({
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
        state: { insufficientStock: created.insufficient_stock_at_request, requestId: created.id },
      })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearCustomerToken()
        notifyCustomerAuthChanged()
        setCustomerToken(null)
        goLogin()
        return
      }
      setError(err instanceof ApiError ? err.message : 'Не удалось отправить заказ')
    } finally {
      setSaving(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (cart.length === 0 || saving) return
    const token = loadCustomerToken()
    if (!token) {
      goLogin()
      return
    }
    await submit(token, note)
  }

  async function saveName() {
    const name = nameDraft.trim()
    if (!profile || !name) {
      setEditingName(false)
      return
    }
    try {
      await updateCustomerProfile({ name })
      setProfile({ ...profile, name })
      setEditingName(false)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить имя')
    }
  }

  if (cart.length === 0) {
    return (
      <main className={styles.page}>
        <h1 className={styles.title}>Корзина</h1>
        <EmptyState
          illustration="empty-cart"
          title="Корзина пуста"
          description="Добавьте товары из каталога — здесь можно будет оформить заказ."
          actionLabel="В каталог"
          onAction={() => navigate(`/store/${slug}`)}
        />
      </main>
    )
  }

  return (
    <main className={styles.page}>
      <div className={styles.titleRow}>
        <h1 className={styles.title}>Корзина</h1>
        <span className={styles.count}>
          {positions} {plural(positions, ['товар', 'товара', 'товаров'])}
        </span>
      </div>

      <form className={styles.layout} onSubmit={handleSubmit}>
        <ul className={styles.list}>
          {cart.map((item, index) => {
            const qty = Number(item.quantity || 0)
            return (
              <li key={`${item.product_id}-${item.variant_id ?? 'x'}`} className={styles.item}>
                <Link to={`/store/${slug}/products/${item.product_id}`} className={styles.photo} tabIndex={-1}>
                  <ProductPhoto src={item.photo} size={80} />
                </Link>
                <div className={styles.itemBody}>
                  <div className={styles.itemHead}>
                    <Link to={`/store/${slug}/products/${item.product_id}`} className={styles.itemName}>
                      {item.name}
                    </Link>
                    <button
                      type="button"
                      className={styles.remove}
                      onClick={() => removeItem(index)}
                      aria-label={`Убрать «${item.name}» из корзины`}
                    >
                      <IconTrash size={20} stroke={1.8} />
                    </button>
                  </div>
                  {item.variant_label && <span className={styles.itemMeta}>{item.variant_label}</span>}
                  <span className={styles.itemMeta}>{formatMoney(item.retail_price)} ₽ за 1</span>
                  <div className={styles.itemFooter}>
                    <QtyStepper
                      value={item.quantity}
                      onStep={(d) => stepQty(index, d)}
                      onDirectInput={(raw) => typeQty(index, raw)}
                      inputAriaLabel={`Количество: ${item.name}`}
                      disableDecrease={qty <= minQty(item)}
                      inputMode="decimal"
                    />
                    <strong className={styles.lineTotal}>{formatMoney(Number(item.retail_price) * qty)} ₽</strong>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>

        <aside className={styles.summary}>
          <section className={styles.card}>
            <h2 className={styles.cardTitle}>Ваш заказ</h2>
            <div className={`${styles.summaryRow} ${styles.summaryTotal}`}>
              <span>Итого</span>
              <span>{formatMoney(total)} ₽</span>
            </div>
            <p className={styles.hint}>
              <IconInfoCircle size={18} stroke={1.8} />
              Магазин подтвердит наличие и напишет вам. Оплата — при получении.
            </p>
          </section>

          <section className={styles.card}>
            <h2 className={styles.cardTitle}>Кто заказывает</h2>
            {customerToken && profile ? (
              editingName ? (
                <div className={styles.nameEdit}>
                  <input
                    value={nameDraft}
                    onChange={(e) => setNameDraft(e.target.value)}
                    maxLength={200}
                    placeholder="Как к вам обращаться"
                    aria-label="Имя"
                    autoFocus
                  />
                  <Button type="button" onClick={saveName}>
                    Сохранить
                  </Button>
                </div>
              ) : (
                <div className={styles.who}>
                  <IconUserCircle size={28} stroke={1.6} className={styles.whoIcon} />
                  <div className={styles.whoText}>
                    <strong>{displayName(profile)}</strong>
                    {displayName(profile) !== profile.phone && <span>{profile.phone}</span>}
                  </div>
                  <button
                    type="button"
                    className={styles.linkButton}
                    onClick={() => {
                      setNameDraft(profile.name)
                      setEditingName(true)
                    }}
                  >
                    {profile.name.trim() ? 'Изменить' : 'Указать имя'}
                  </button>
                </div>
              )
            ) : (
              <p className={styles.hint}>
                <IconUserCircle size={18} stroke={1.8} />
                Войдите или зарегистрируйтесь — магазину нужен ваш телефон, чтобы связаться.
              </p>
            )}

            {noteOpen ? (
              <label className={styles.noteField}>
                Комментарий для магазина
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={1000}
                  rows={3}
                  placeholder="Например: заберу завтра после обеда"
                  autoFocus
                />
              </label>
            ) : (
              <button type="button" className={styles.noteToggle} onClick={() => setNoteOpen(true)}>
                <IconChevronDown size={18} stroke={1.8} />
                Добавить комментарий
              </button>
            )}
          </section>

          {error && (
            <p ref={errorRef} className={styles.error} role="alert">
              {error}
            </p>
          )}

          <div className={styles.submitBar}>
            <div className={styles.submitTotal}>
              <span>Итого</span>
              <strong>{formatMoney(total)} ₽</strong>
            </div>
            <Button type="submit" className={styles.submit} disabled={saving}>
              {saving ? 'Отправляем…' : customerToken ? 'Оформить заказ' : 'Войти и оформить'}
            </Button>
          </div>
        </aside>
      </form>
    </main>
  )
}
