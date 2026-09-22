import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  getStorefrontProduct,
  getStorefrontShopProfileCached,
  type StorefrontProductDetail,
} from '../../entities/storefront/api'
import { ApiError } from '../../shared/api/client'
import {
  FAVORITES_PREFIX,
  addFavorite,
  loadAllFavorites,
  removeFavorite,
} from '../../shared/lib/favorites'
import { plural } from '../../shared/lib/format'
import { setPageMeta, resetPageMeta } from '../../shared/lib/pageMeta'
import { EmptyState } from '../../shared/ui/EmptyState'
import { ErrorState } from '../../shared/ui/ErrorState'
import { ProductGrid } from './ProductGrid'
import styles from './FavoritesPage.module.css'

/** Одновременных запросов за товарами — избранное может быть большим,
 *  но браузер и так ограничивает пул соединений, а витрина не должна
 *  получать всплеск запросов от одной вкладки. */
const CONCURRENCY = 6

/** Сколько тост «Убрали из избранного» ждёт нажатия «Вернуть». */
const UNDO_MS = 5000

interface FavoriteItem {
  slug: string
  product: StorefrontProductDetail
}

interface ShopInfo {
  slug: string
  name: string
  logo: string
}

interface ShopGroup {
  shop: ShopInfo
  items: FavoriteItem[]
}

/** Выполняет задачи пачками не больше limit одновременно. */
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
  | { kind: 'item'; item: FavoriteItem }
  | { kind: 'gone' }
  | { kind: 'failed' }

/**
 * Общая страница избранного по всем магазинам сразу.
 *
 * Данные лежат в localStorage отдельным ключом на магазин, самого списка
 * товаров на бэкенде нет — поэтому каждый товар догружается точечно через
 * публичный /storefront/{slug}/products/{id}. Маркетплейсный эндпоинт не
 * используем: общая витрина отключена флагом и отдаёт 404.
 */
export function FavoritesPage() {
  const [groups, setGroups] = useState<ShopGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  // index — позиция карточки в группе, чтобы «Вернуть» поставил товар на место,
  // а не в конец сетки
  const [undo, setUndo] = useState<{ slug: string; product: StorefrontProductDetail; index: number } | null>(
    null,
  )
  const undoTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  // перезагрузка страницы по кнопке «Повторить» и по событию из другой вкладки
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    setPageMeta({ title: 'Избранное — ВайСклад' })
    return () => resetPageMeta()
  }, [])

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setFailed(false)

      const entries = loadAllFavorites()
      if (entries.length === 0) {
        if (!cancelled) {
          setGroups([])
          setLoading(false)
        }
        return
      }

      const pairs = entries.flatMap((entry) => entry.ids.map((id) => ({ slug: entry.slug, id })))
      const tasks = pairs.map(({ slug, id }) => async (): Promise<LoadOutcome> => {
        try {
          const page = await getStorefrontProduct(slug, id)
          return { kind: 'item', item: { slug, product: page.product } }
        } catch (err) {
          // 404 — товар снят с витрины или магазин выключил витрину целиком:
          // молча убираем из localStorage, показывать «битую» карточку нечем
          if (err instanceof ApiError && err.status === 404) {
            removeFavorite(slug, id)
            return { kind: 'gone' }
          }
          return { kind: 'failed' }
        }
      })

      const outcomes = await runPooled(tasks, CONCURRENCY)
      if (cancelled) return

      const items = outcomes.flatMap((o) => (o.kind === 'item' ? [o.item] : []))
      const anyFailed = outcomes.some((o) => o.kind === 'failed')

      // сеть лежит и не загрузилось вообще ничего — показываем «Повторить».
      // Если часть товаров пришла, экран полезен: рисуем что есть.
      if (items.length === 0 && anyFailed) {
        setGroups([])
        setFailed(true)
        setLoading(false)
        return
      }

      const slugs = [...new Set(items.map((i) => i.slug))]
      const shops = await Promise.all(
        slugs.map(async (slug): Promise<ShopInfo> => {
          try {
            // общий кэш с PublicHeader — один запрос профиля на магазин за визит
            const profile = await getStorefrontShopProfileCached(slug)
            return { slug, name: profile.name, logo: profile.logo }
          } catch {
            // профиль недоступен — группа всё равно нужна, подписываем слагом
            return { slug, name: slug, logo: '' }
          }
        }),
      )
      if (cancelled) return

      const next = shops
        .map((shop) => ({ shop, items: items.filter((i) => i.slug === shop.slug) }))
        .sort((a, b) => a.shop.name.localeCompare(b.shop.name, 'ru'))

      setGroups(next)
      setLoading(false)
    }

    load()
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  // другая вкладка изменила избранное — перечитываем список.
  // Собственные изменения этой страницы в перезагрузке не нуждаются: карточка
  // убирается из состояния сразу (handleRemove), поэтому FAVORITES_EVENT здесь
  // не слушаем — иначе каждое снятие сердечка запускало бы полный перезапрос.
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key != null && !e.key.startsWith(FAVORITES_PREFIX)) return
      setReloadKey((k) => k + 1)
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  useEffect(() => () => {
    if (undoTimer.current) clearTimeout(undoTimer.current)
  }, [])

  const dropItem = useCallback((slug: string, productId: number) => {
    setGroups((prev) =>
      prev
        .map((g) => (g.shop.slug === slug ? { ...g, items: g.items.filter((i) => i.product.id !== productId) } : g))
        .filter((g) => g.items.length > 0),
    )
  }, [])

  function handleRemove(slug: string, product: StorefrontProductDetail) {
    const index = groups
      .find((g) => g.shop.slug === slug)
      ?.items.findIndex((i) => i.product.id === product.id)
    removeFavorite(slug, product.id)
    dropItem(slug, product.id)
    if (undoTimer.current) clearTimeout(undoTimer.current)
    setUndo({ slug, product, index: index != null && index >= 0 ? index : 0 })
    undoTimer.current = setTimeout(() => setUndo(null), UNDO_MS)
  }

  function handleUndo() {
    if (!undo) return
    const { slug, product, index } = undo
    addFavorite(slug, product.id)
    setUndo(null)
    if (undoTimer.current) clearTimeout(undoTimer.current)
    // товар возвращаем из памяти, без повторного запроса к витрине.
    // Группа магазина исчезла вместе с последним его товаром — тогда имя и
    // логотип магазина взять неоткуда, перезагружаем страницу целиком.
    const group = groups.find((g) => g.shop.slug === slug)
    if (!group) {
      setReloadKey((k) => k + 1)
      return
    }
    if (group.items.some((i) => i.product.id === product.id)) return
    setGroups((prev) =>
      prev.map((g) => {
        if (g.shop.slug !== slug) return g
        const items = [...g.items]
        items.splice(Math.min(index, items.length), 0, { slug, product })
        return { ...g, items }
      }),
    )
  }

  const total = groups.reduce((sum, g) => sum + g.items.length, 0)

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

  if (total === 0) {
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

  const single = groups.length === 1

  return (
    <div className={styles.shell}>
      <div className={styles.head}>
        <h1 className={styles.title}>Избранное</h1>
        <span className={styles.count}>
          {total} {plural(total, ['товар', 'товара', 'товаров'])}
        </span>
      </div>

      {single ? (
        <ProductGrid
          items={groups[0].items.map((i) => i.product)}
          getHref={(item) => `/store/${groups[0].shop.slug}/products/${item.id}`}
          favorites={groups[0].items.map((i) => i.product.id)}
          onToggleFavorite={(item) => handleRemove(groups[0].shop.slug, item)}
        />
      ) : (
        groups.map((group) => (
          <section key={group.shop.slug} className={styles.group}>
            <Link to={`/store/${group.shop.slug}`} className={styles.shopRow}>
              {group.shop.logo ? (
                <img src={group.shop.logo} alt="" width={40} height={40} className={styles.shopLogo} />
              ) : (
                <span className={styles.shopLogoFallback} aria-hidden="true">
                  {group.shop.name.charAt(0).toUpperCase()}
                </span>
              )}
              <span className={styles.shopName}>{group.shop.name}</span>
              <span className={styles.shopCount}>
                {group.items.length} {plural(group.items.length, ['товар', 'товара', 'товаров'])}
              </span>
            </Link>
            <ProductGrid
              items={group.items.map((i) => i.product)}
              getHref={(item) => `/store/${group.shop.slug}/products/${item.id}`}
              favorites={group.items.map((i) => i.product.id)}
              onToggleFavorite={(item) => handleRemove(group.shop.slug, item)}
            />
          </section>
        ))
      )}

      {renderToast()}
    </div>
  )

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
}
