import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  getStorefrontProduct,
  getStorefrontShopProfileCached,
  peekCachedStorefrontShopProfile,
  type StorefrontProductDetail,
} from '../../entities/storefront/api'
import { ApiError } from '../../shared/api/client'
import {
  FAVORITES_PREFIX,
  addFavorite,
  loadFavorites,
  removeFavorite,
} from '../../shared/lib/favorites'
import { plural } from '../../shared/lib/format'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { EmptyState } from '../../shared/ui/EmptyState'
import { ErrorState } from '../../shared/ui/ErrorState'
import { ProductGrid } from './ProductGrid'
import styles from './FavoritesPage.module.css'

const CONCURRENCY = 6
const UNDO_MS = 5000

async function runPooled<T>(tasks: (() => Promise<T>)[], limit: number): Promise<T[]> {
  const results = new Array<T>(tasks.length)
  let next = 0
  async function worker() {
    while (next < tasks.length) {
      const index = next++
      results[index] = await tasks[index]()
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, tasks.length) }, worker))
  return results
}

type LoadOutcome =
  | { kind: 'item'; product: StorefrontProductDetail }
  | { kind: 'gone' }
  | { kind: 'failed' }

/**
 * Избранное одного магазина — /store/:slug/favorites.
 * Ключ localStorage: waysklad:storefront-favorites:<slug>.
 */
export function FavoritesPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  const [items, setItems] = useState<StorefrontProductDetail[]>([])
  const [shopName, setShopName] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [undo, setUndo] = useState<{ product: StorefrontProductDetail; index: number } | null>(null)
  const undoTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    const cached = peekCachedStorefrontShopProfile(slug)
    if (cached) setShopName(cached.name)
    else {
      getStorefrontShopProfileCached(slug)
        .then((p) => setShopName(p.name))
        .catch(() => setShopName(null))
    }
  }, [slug])

  useEffect(() => {
    const title = shopName ? `Избранное — ${shopName}` : 'Избранное'
    setPageMeta({ title })
    return () => resetPageMeta()
  }, [shopName])

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setFailed(false)

      const ids = loadFavorites(slug)
      if (ids.length === 0) {
        if (!cancelled) {
          setItems([])
          setLoading(false)
        }
        return
      }

      const tasks = ids.map((id) => async (): Promise<LoadOutcome> => {
        try {
          const page = await getStorefrontProduct(slug, id)
          return { kind: 'item', product: page.product }
        } catch (err) {
          if (err instanceof ApiError && err.status === 404) {
            removeFavorite(slug, id)
            return { kind: 'gone' }
          }
          return { kind: 'failed' }
        }
      })

      const outcomes = await runPooled(tasks, CONCURRENCY)
      if (cancelled) return

      const products = outcomes.flatMap((o) => (o.kind === 'item' ? [o.product] : []))
      const anyFailed = outcomes.some((o) => o.kind === 'failed')

      if (products.length === 0 && anyFailed) {
        setItems([])
        setFailed(true)
        setLoading(false)
        return
      }

      setItems(products)
      setLoading(false)
    }

    load()
    return () => {
      cancelled = true
    }
  }, [slug, reloadKey])

  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key != null && e.key !== `${FAVORITES_PREFIX}${slug}`) return
      setReloadKey((k) => k + 1)
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [slug])

  useEffect(
    () => () => {
      if (undoTimer.current) clearTimeout(undoTimer.current)
    },
    [],
  )

  const dropItem = useCallback((productId: number) => {
    setItems((prev) => prev.filter((p) => p.id !== productId))
  }, [])

  function handleRemove(product: StorefrontProductDetail) {
    const index = items.findIndex((p) => p.id === product.id)
    removeFavorite(slug, product.id)
    dropItem(product.id)
    if (undoTimer.current) clearTimeout(undoTimer.current)
    setUndo({ product, index: index >= 0 ? index : 0 })
    undoTimer.current = setTimeout(() => setUndo(null), UNDO_MS)
  }

  function handleUndo() {
    if (!undo) return
    const { product, index } = undo
    addFavorite(slug, product.id)
    setUndo(null)
    if (undoTimer.current) clearTimeout(undoTimer.current)
    setItems((prev) => {
      if (prev.some((p) => p.id === product.id)) return prev
      const next = [...prev]
      next.splice(Math.min(index, next.length), 0, product)
      return next
    })
  }

  function renderToast() {
    if (!undo) return null
    return (
      <div className={styles.toast} role="status">
        <span>Убрали из избранного</span>
        <button type="button" className={styles.toastAction} onClick={handleUndo}>
          Вернуть
        </button>
      </div>
    )
  }

  if (loading) {
    return (
      <div className={styles.shell}>
        <h1 className={styles.title}>Избранное</h1>
        <ProductGrid items={[]} getHref={() => ''} loading skeletonCount={8} />
      </div>
    )
  }

  if (failed) {
    return (
      <div className={styles.shell}>
        <h1 className={styles.title}>Избранное</h1>
        <ErrorState
          illustration="error-404-not-found"
          title="Не удалось загрузить избранное"
          description="Проверьте соединение и попробуйте ещё раз."
          actionLabel="Повторить"
          onAction={() => setReloadKey((k) => k + 1)}
        />
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className={styles.shell}>
        <h1 className={styles.title}>Избранное</h1>
        <EmptyState
          illustration="empty-box"
          title="В избранном пока пусто"
          description="Нажмите ♡ на товаре, чтобы сохранить его здесь"
        />
        {renderToast()}
      </div>
    )
  }

  return (
    <div className={styles.shell}>
      <div className={styles.head}>
        <h1 className={styles.title}>Избранное</h1>
        <span className={styles.count}>
          {items.length} {plural(items.length, ['товар', 'товара', 'товаров'])}
        </span>
      </div>

      <ProductGrid
        items={items}
        getHref={(item) => `/store/${slug}/products/${item.id}`}
        favorites={items.map((i) => i.id)}
        onToggleFavorite={(item) => handleRemove(item)}
      />

      {renderToast()}
    </div>
  )
}
