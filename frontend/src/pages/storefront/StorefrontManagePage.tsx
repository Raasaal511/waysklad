import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  IconBuildingStore,
  IconExternalLink,
  IconCopy,
  IconCheck,
  IconSearch,
  IconEye,
  IconEyeOff,
  IconTrash,
  IconPhoto,
} from '@tabler/icons-react'
import { updateShop, uploadShopLogo, deleteShopLogo } from '../../entities/profile/api'
import { listProducts, updateProduct, type Product } from '../../entities/product/api'
import { useAuth } from '../../app/AuthContext'
import { useShop } from '../../app/ShopContext'
import { useCatalog } from '../../app/CatalogContext'
import { ApiError } from '../../shared/api/client'
import { formatMoney } from '../../shared/lib/format'
import { Button } from '../../shared/ui/Button'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
import { PhoneInput } from '../../shared/ui/PhoneInput'
import { StorefrontRequestsPanel } from './StorefrontRequestsPage'
import layoutStyles from '../../shared/ui/Layout.module.css'
import styles from './StorefrontManagePage.module.css'

type Tab = 'settings' | 'products' | 'requests'

export function StorefrontManagePage() {
  const { user } = useAuth()
  const canSettings = user?.role === 'owner'
  const canProducts = user?.role === 'owner' || user?.role === 'manager'
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab') as Tab | null
  const tab: Tab =
    tabParam === 'products' || tabParam === 'requests' || tabParam === 'settings'
      ? tabParam
      : 'settings'

  function setTab(next: Tab) {
    setSearchParams(next === 'settings' ? {} : { tab: next }, { replace: true })
  }

  const tabs: { id: Tab; label: string; show: boolean }[] = [
    { id: 'settings', label: 'Настройки', show: true },
    { id: 'products', label: 'Товары на витрине', show: canProducts },
    { id: 'requests', label: 'Заявки', show: true },
  ]

  return (
    <div className={layoutStyles.stack}>
      <div className={layoutStyles.sectionTitle}>
        <div className={layoutStyles.row} style={{ gap: 8 }}>
          <IconBuildingStore size={22} stroke={1.8} />
          <h2>Витрина</h2>
        </div>
      </div>

      <div className="sale-period-tabs">
        {tabs
          .filter((t) => t.show)
          .map((t) => (
            <Button key={t.id} variant="secondary" active={tab === t.id} onClick={() => setTab(t.id)}>
              {t.label}
            </Button>
          ))}
      </div>

      {tab === 'settings' && <SettingsTab canEdit={canSettings} />}
      {tab === 'products' && canProducts && <ProductsTab />}
      {tab === 'requests' && <StorefrontRequestsPanel embedded />}
    </div>
  )
}

function SettingsTab({ canEdit }: { canEdit: boolean }) {
  const { shop, setShop, setShopName } = useShop()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  if (!shop) return <p className={layoutStyles.textMuted}>Загрузка…</p>

  const storeUrl = shop.slug ? `${window.location.origin}/store/${shop.slug}` : null

  async function toggle(enabled: boolean) {
    if (!canEdit) return
    setError(null)
    setSaving(true)
    try {
      const updated = await updateShop({ name: shop!.name, storefront_enabled: enabled })
      setShop(updated)
      setShopName(updated.name)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить')
    } finally {
      setSaving(false)
    }
  }

  async function copyLink() {
    if (!storeUrl) return
    try {
      await navigator.clipboard.writeText(storeUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError('Не удалось скопировать ссылку')
    }
  }

  return (
    <div className={styles.layout}>
      <section className={styles.heroCard}>
        <div className={styles.heroText}>
          <p className={styles.eyebrow}>Публичный каталог</p>
          <h3>Как видят вас покупатели</h3>
          <p className={layoutStyles.textMuted}>
            Витрина — отдельная страница без входа. Покупатель выбирает товары и оставляет заявку,
            а вы принимаете её как обычный заказ.
          </p>
        </div>
        <div className={styles.statusBlock}>
          <span className={shop.storefront_enabled ? styles.statusOn : styles.statusOff}>
            {shop.storefront_enabled ? 'Включена' : 'Выключена'}
          </span>
          {canEdit ? (
            <label className={styles.switchRow}>
              <input
                type="checkbox"
                checked={shop.storefront_enabled}
                disabled={saving}
                onChange={(e) => toggle(e.target.checked)}
              />
              Показывать витрину покупателям
            </label>
          ) : (
            <p className={layoutStyles.textMuted}>Включить витрину может только владелец</p>
          )}
        </div>
      </section>

      {shop.storefront_enabled && storeUrl && (
        <section className={[layoutStyles.card, layoutStyles.cardFull, layoutStyles.stack].join(' ')}>
          <div>
            <h3>Ссылка для клиентов</h3>
            <p className={layoutStyles.textMuted}>
              Поставьте в шапку Instagram / WhatsApp / QR на витрине.
            </p>
          </div>
          <code className={styles.linkBox}>{storeUrl}</code>
          <div className={layoutStyles.row} style={{ gap: 8, flexWrap: 'wrap' }}>
            <Button variant="secondary" onClick={copyLink}>
              {copied ? <IconCheck size={16} stroke={1.8} /> : <IconCopy size={16} stroke={1.8} />}
              {copied ? 'Скопировано' : 'Копировать'}
            </Button>
            <a href={storeUrl} target="_blank" rel="noreferrer">
              <Button variant="secondary">
                <IconExternalLink size={16} stroke={1.8} /> Открыть витрину
              </Button>
            </a>
            <Link to="/storefront?tab=products">
              <Button>Выбрать товары →</Button>
            </Link>
          </div>
          <p className={layoutStyles.textMuted} style={{ margin: 0, fontSize: 13 }}>
            Чтобы наличие считалось верно, в настройках склада включите «Показывать на витрине».
            Иначе покупатель увидит товары, но без наличия.
          </p>
        </section>
      )}

      {shop.storefront_enabled && !shop.slug && (
        <p className={layoutStyles.textMuted}>У магазина ещё нет публичного адреса (slug).</p>
      )}

      {!shop.storefront_enabled && (
        <section className={[layoutStyles.card, layoutStyles.cardFull].join(' ')}>
          <p className={layoutStyles.textMuted} style={{ margin: 0 }}>
            После включения откройте вкладку «Товары на витрине» и отметьте, что показывать покупателям.
            По умолчанию все товары скрыты.
          </p>
        </section>
      )}

      {error && <p className={layoutStyles.error}>{error}</p>}

      {canEdit && shop.storefront_enabled && <ShopProfileSection />}
    </div>
  )
}

const FAQ_FIELDS: { key: 'policy_refund_money' | 'policy_payment' | 'policy_delivery' | 'policy_returns'; label: string }[] = [
  { key: 'policy_refund_money', label: 'Возврат денег' },
  { key: 'policy_payment', label: 'Способы оплаты' },
  { key: 'policy_delivery', label: 'Условия доставки' },
  { key: 'policy_returns', label: 'Возврат товаров' },
]

/** Профиль витрины: логотип, описание, контакты, мин. сумма заказа, точный остаток, тексты FAQ. */
function ShopProfileSection() {
  const { shop, setShop } = useShop()
  const logoInputRef = useRef<HTMLInputElement>(null)
  const [description, setDescription] = useState(shop?.storefront_description ?? '')
  const [phone, setPhone] = useState(shop?.contact_phone ?? '')
  const [whatsapp, setWhatsapp] = useState(shop?.contact_whatsapp ?? '')
  const [telegram, setTelegram] = useState(shop?.contact_telegram ?? '')
  const [minOrderTotal, setMinOrderTotal] = useState(shop?.storefront_min_order_total ?? '')
  const [showStockQty, setShowStockQty] = useState(shop?.storefront_show_stock_qty ?? false)
  const [policies, setPolicies] = useState({
    policy_refund_money: shop?.policy_refund_money ?? '',
    policy_payment: shop?.policy_payment ?? '',
    policy_delivery: shop?.policy_delivery ?? '',
    policy_returns: shop?.policy_returns ?? '',
  })
  const [logoUploading, setLogoUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!shop) return null

  async function handleLogoUpload(file: File) {
    setLogoUploading(true)
    setError(null)
    try {
      const updated = await uploadShopLogo(file)
      setShop(updated)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить логотип')
    } finally {
      setLogoUploading(false)
    }
  }

  async function handleLogoDelete() {
    setLogoUploading(true)
    setError(null)
    try {
      const updated = await deleteShopLogo()
      setShop(updated)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось удалить логотип')
    } finally {
      setLogoUploading(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const updated = await updateShop({
        name: shop!.name,
        storefront_description: description,
        contact_phone: phone,
        contact_whatsapp: whatsapp,
        contact_telegram: telegram,
        storefront_min_order_total: minOrderTotal || null,
        storefront_show_stock_qty: showStockQty,
        ...policies,
      })
      setShop(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className={[layoutStyles.card, layoutStyles.cardFull, layoutStyles.stack].join(' ')}>
      <h3>Профиль витрины</h3>
      <p className={layoutStyles.textMuted} style={{ margin: 0 }}>
        Эти данные видят покупатели на карточке товара — логотип, контакты, минимальная сумма заказа
        и ответы на частые вопросы.
      </p>

      <div className={layoutStyles.row} style={{ gap: 16, alignItems: 'center' }}>
        {shop.logo ? (
          <img src={shop.logo} alt="" style={{ width: 64, height: 64, borderRadius: '50%', objectFit: 'cover' }} />
        ) : (
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'var(--accent-soft)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent)',
            }}
          >
            <IconPhoto size={24} stroke={1.8} />
          </div>
        )}
        <div className={layoutStyles.row} style={{ gap: 8 }}>
          <Button
            type="button"
            variant="secondary"
            onClick={() => logoInputRef.current?.click()}
            disabled={logoUploading}
          >
            {shop.logo ? 'Заменить логотип' : 'Загрузить логотип'}
          </Button>
          {shop.logo && (
            <Button type="button" variant="danger" onClick={handleLogoDelete} disabled={logoUploading}>
              <IconTrash size={14} stroke={1.8} /> Удалить
            </Button>
          )}
          <input
            ref={logoInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0]
              e.target.value = ''
              if (file) handleLogoUpload(file)
            }}
          />
        </div>
      </div>

      <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <span className={layoutStyles.textMuted}>Описание магазина</span>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value.slice(0, 500))}
          rows={3}
          maxLength={500}
        />
        <span className={layoutStyles.textMuted} style={{ fontSize: 12, alignSelf: 'flex-end' }}>
          {description.length} / 500
        </span>
      </label>

      <div className={layoutStyles.row} style={{ gap: 12, flexWrap: 'wrap' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: '1 1 200px' }}>
          <span className={layoutStyles.textMuted}>Телефон</span>
          <PhoneInput value={phone} onChange={setPhone} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: '1 1 200px' }}>
          <span className={layoutStyles.textMuted}>WhatsApp</span>
          <PhoneInput value={whatsapp} onChange={setWhatsapp} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: '1 1 200px' }}>
          <span className={layoutStyles.textMuted}>Telegram (без @)</span>
          <input value={telegram} onChange={(e) => setTelegram(e.target.value.replace(/^@/, ''))} placeholder="username" />
        </label>
      </div>

      <div className={layoutStyles.row} style={{ gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span className={layoutStyles.textMuted}>Минимальная сумма заказа</span>
          <input
            type="text"
            inputMode="decimal"
            value={minOrderTotal}
            onChange={(e) => setMinOrderTotal(e.target.value)}
            placeholder="без ограничения"
          />
        </label>
        {minOrderTotal && (
          <Button type="button" variant="secondary" onClick={() => setMinOrderTotal('')}>
            Убрать лимит
          </Button>
        )}
      </div>

      <label className={styles.switchRow}>
        <input type="checkbox" checked={showStockQty} onChange={(e) => setShowStockQty(e.target.checked)} />
        Показывать точный остаток на витрине
      </label>

      <div className={layoutStyles.stack}>
        <h4 style={{ margin: 0 }}>Часто задаваемые вопросы</h4>
        {FAQ_FIELDS.map((f) => (
          <label key={f.key} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className={layoutStyles.textMuted}>{f.label}</span>
            <textarea
              value={policies[f.key]}
              onChange={(e) => setPolicies((p) => ({ ...p, [f.key]: e.target.value.slice(0, 5000) }))}
              rows={3}
              maxLength={5000}
            />
            <span className={layoutStyles.textMuted} style={{ fontSize: 12, alignSelf: 'flex-end' }}>
              {policies[f.key].length} / 5000
            </span>
          </label>
        ))}
      </div>

      {error && <p className={layoutStyles.error}>{error}</p>}

      <Button type="button" onClick={handleSave} disabled={saving}>
        {saving ? 'Сохранение…' : saved ? 'Сохранено' : 'Сохранить'}
      </Button>
    </section>
  )
}

function ProductsTab() {
  const { refresh } = useCatalog()
  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [filter, setFilter] = useState<'all' | 'on' | 'off'>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 300)
    return () => clearTimeout(t)
  }, [query])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const { items, total: t } = await listProducts({
        query: debounced,
        limit: 50,
        offset: 0,
        sort: 'name',
      })
      setProducts(items)
      setTotal(t)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось загрузить товары')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced])

  const visible = useMemo(() => {
    if (filter === 'on') return products.filter((p) => p.show_on_storefront)
    if (filter === 'off') return products.filter((p) => !p.show_on_storefront)
    return products
  }, [products, filter])

  const onCount = products.filter((p) => p.show_on_storefront).length

  const offCount = products.length - onCount

  async function toggleProduct(product: Product) {
    setBusyId(product.id)
    setError(null)
    try {
      const next = !product.show_on_storefront
      const saved = await updateProduct(product.id, {
        name: product.name,
        unit_code: product.unit_code,
        purchase_price: product.purchase_price ?? '0',
        retail_price: product.retail_price,
        sku: product.sku,
        barcode: product.barcode,
        category_id: product.category_id,
        min_stock: product.min_stock,
        show_on_storefront: next,
        photo: product.photo,
        variants: product.variants.map((v) => ({
          id: v.id,
          size: v.size,
          color: v.color,
          barcode: v.barcode,
          name: v.name,
        })),
      })
      setProducts((prev) => prev.map((p) => (p.id === saved.id ? saved : p)))
      refresh(['products']).catch(() => {})
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось обновить товар')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className={layoutStyles.stack}>
      <p className={layoutStyles.textMuted}>
        Отметьте товары, которые покупатель увидит на витрине. Остальные останутся только во
        внутреннем каталоге.
      </p>

      <div className={styles.productsToolbar}>
        <label className={styles.search}>
          <IconSearch size={16} stroke={1.8} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск по названию, артикулу…"
          />
        </label>
        <div className={styles.filterTabs} role="tablist" aria-label="Фильтр витрины">
          {(
            [
              ['all', 'Все', products.length],
              ['on', 'На витрине', onCount],
              ['off', 'Скрыты', offCount],
            ] as const
          ).map(([id, label, count]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={filter === id}
              className={[styles.filterTab, filter === id && styles.filterTabActive]
                .filter(Boolean)
                .join(' ')}
              onClick={() => setFilter(id)}
            >
              <span>{label}</span>
              <span className={styles.filterCount}>{count}</span>
            </button>
          ))}
        </div>
      </div>

      {error && <p className={layoutStyles.error}>{error}</p>}
      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : visible.length === 0 ? (
        <p className={layoutStyles.textMuted}>Нет товаров по фильтру</p>
      ) : (
        <div className={styles.productGrid}>
          {visible.map((p) => {
            const onShowcase = p.show_on_storefront
            return (
              <div
                key={p.id}
                className={[styles.productCard, onShowcase && styles.productCardOn]
                  .filter(Boolean)
                  .join(' ')}
              >
                <div className={styles.productCardPhoto}>
                  <ProductPhoto src={p.photo} size={160} />
                </div>
                <div className={styles.productMeta}>
                  <strong className={styles.productName}>{p.name}</strong>
                  <div className={styles.productDetails}>
                    <span className={styles.productPrice}>
                      {formatMoney(p.retail_price)}
                      <span className={styles.productCurrency}>₽</span>
                    </span>
                    {p.sku && <span className={styles.productSku}>арт. {p.sku}</span>}
                  </div>
                </div>
                <button
                  type="button"
                  className={onShowcase ? styles.toggleOn : styles.toggleOff}
                  disabled={busyId === p.id}
                  onClick={() => toggleProduct(p)}
                  aria-pressed={onShowcase}
                >
                  {onShowcase ? (
                    <>
                      <IconEye size={16} stroke={1.8} /> На витрине
                    </>
                  ) : (
                    <>
                      <IconEyeOff size={16} stroke={1.8} /> Скрыт
                    </>
                  )}
                </button>
              </div>
            )
          })}
        </div>
      )}
      {!loading && total > products.length && (
        <p className={layoutStyles.textMuted}>
          Показано {products.length} из {total}. Уточните поиск, если нужного товара нет в списке.
        </p>
      )}
    </div>
  )
}
