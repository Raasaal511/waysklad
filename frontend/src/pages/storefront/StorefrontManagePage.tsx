import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  IconBuildingStore,
  IconExternalLink,
  IconCopy,
  IconCheck,
  IconSearch,
  IconEye,
  IconEyeOff,
} from '@tabler/icons-react'
import { updateShop } from '../../entities/profile/api'
import { listProducts, updateProduct, type Product } from '../../entities/product/api'
import { useAuth } from '../../app/AuthContext'
import { useShop } from '../../app/ShopContext'
import { useCatalog } from '../../app/CatalogContext'
import { ApiError } from '../../shared/api/client'
import { formatMoney } from '../../shared/lib/format'
import { Button } from '../../shared/ui/Button'
import { ProductPhoto } from '../../shared/ui/ProductPhoto'
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
    </div>
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
        <div className={layoutStyles.row} style={{ gap: 6 }}>
          {(
            [
              ['all', `Все · ${products.length}`],
              ['on', `На витрине · ${onCount}`],
              ['off', 'Скрыты'],
            ] as const
          ).map(([id, label]) => (
            <Button
              key={id}
              variant="secondary"
              active={filter === id}
              onClick={() => setFilter(id)}
            >
              {label}
            </Button>
          ))}
        </div>
      </div>

      {error && <p className={layoutStyles.error}>{error}</p>}
      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : visible.length === 0 ? (
        <p className={layoutStyles.textMuted}>Нет товаров по фильтру</p>
      ) : (
        <div className={styles.productList}>
          {visible.map((p) => (
            <div key={p.id} className={styles.productRow}>
              <ProductPhoto src={p.photo} size={36} />
              <div className={styles.productMeta}>
                <strong>{p.name}</strong>
                <span className={layoutStyles.textMuted}>
                  {formatMoney(p.retail_price)} ₽
                  {p.sku ? ` · ${p.sku}` : ''}
                </span>
              </div>
              <button
                type="button"
                className={p.show_on_storefront ? styles.toggleOn : styles.toggleOff}
                disabled={busyId === p.id}
                onClick={() => toggleProduct(p)}
              >
                {p.show_on_storefront ? (
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
          ))}
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
