import { useEffect, useRef, useState } from 'react'
import {
  getSimilarProducts,
  getStorefrontProduct,
  getStorefrontShopProfileCached,
  peekCachedStorefrontShopProfile,
  trackProductView,
  type SimilarProductsResponse,
  type SimilarScope,
  type StorefrontProductDetail,
  type StorefrontShopProfile,
} from '../../../entities/storefront/api'
import { getProductReviews, type ReviewsPage, type ReviewsQueryParams } from '../../../entities/review/api'
import { ApiError } from '../../../shared/api/client'

interface ProductState {
  product: StorefrontProductDetail | null
  shopName: string
  loading: boolean
  error: string | null
  errorStatus: number | null
}

/** Товар карточки. Отрисовка страницы ждёт только этот хук. */
export function useStorefrontProduct(slug: string, productId: string) {
  const [state, setState] = useState<ProductState>({
    product: null,
    shopName: '',
    loading: true,
    error: null,
    errorStatus: null,
  })

  useEffect(() => {
    let cancelled = false
    setState((s) => ({ ...s, loading: true, error: null, errorStatus: null }))
    async function load() {
      try {
        const data = await getStorefrontProduct(slug, Number(productId))
        if (cancelled) return
        setState({ product: data.product, shopName: data.shop_name, loading: false, error: null, errorStatus: null })
      } catch (err) {
        if (cancelled) return
        const status = err instanceof ApiError ? err.status : null
        const message =
          status === 404
            ? 'Товар не найден или скрыт'
            : status === 403
              ? 'Магазин временно недоступен'
              : err instanceof ApiError
                ? err.message
                : 'Не удалось загрузить товар'
        setState({ product: null, shopName: '', loading: false, error: message, errorStatus: status })
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [slug, productId])

  return state
}

export function useShopProfile(slug: string) {
  const [profile, setProfile] = useState<StorefrontShopProfile | null>(() =>
    peekCachedStorefrontShopProfile(slug),
  )
  const [loading, setLoading] = useState(!profile)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const cached = peekCachedStorefrontShopProfile(slug)
    if (cached) {
      setProfile(cached)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    getStorefrontShopProfileCached(slug)
      .then((data) => {
        if (cancelled) return
        setProfile(data)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить магазин')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [slug])

  return { profile, loading, error }
}

interface ReviewsState {
  page: ReviewsPage | null
  loading: boolean
  loadingMore: boolean
  error: string | null
}

/** Список отзывов со "Показать ещё" (offset). Сброс при смене фильтров. */
export function useProductReviews(slug: string, productId: string, params: ReviewsQueryParams) {
  const [state, setState] = useState<ReviewsState>({ page: null, loading: true, loadingMore: false, error: null })
  const paramsKey = JSON.stringify(params)

  useEffect(() => {
    let cancelled = false
    setState({ page: null, loading: true, loadingMore: false, error: null })
    getProductReviews(slug, Number(productId), { ...params, offset: 0 })
      .then((data) => {
        if (!cancelled) setState({ page: data, loading: false, loadingMore: false, error: null })
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            page: null,
            loading: false,
            loadingMore: false,
            error: err instanceof ApiError ? err.message : 'Не удалось загрузить отзывы',
          })
        }
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, productId, paramsKey])

  async function loadMore() {
    if (!state.page) return
    setState((s) => ({ ...s, loadingMore: true }))
    try {
      const next = await getProductReviews(slug, Number(productId), {
        ...params,
        offset: state.page.reviews.length,
      })
      setState((s) =>
        s.page
          ? { ...s, page: { ...next, reviews: [...s.page.reviews, ...next.reviews] }, loadingMore: false }
          : { ...s, loadingMore: false },
      )
    } catch {
      setState((s) => ({ ...s, loadingMore: false }))
    }
  }

  async function reload() {
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const data = await getProductReviews(slug, Number(productId), { ...params, offset: 0 })
      setState({ page: data, loading: false, loadingMore: false, error: null })
    } catch (err) {
      setState({
        page: null,
        loading: false,
        loadingMore: false,
        error: err instanceof ApiError ? err.message : 'Не удалось загрузить отзывы',
      })
    }
  }

  return { ...state, loadMore, reload }
}

/** Ленивая загрузка похожих товаров по IntersectionObserver. */
export function useSimilar(slug: string, productId: string, scope: SimilarScope) {
  const [ref, setRef] = useState<HTMLElement | null>(null)
  const [data, setData] = useState<SimilarProductsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const triggered = useRef(false)

  useEffect(() => {
    if (!ref || triggered.current) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting) && !triggered.current) {
          triggered.current = true
          setLoading(true)
          getSimilarProducts(slug, Number(productId), scope)
            .then(setData)
            .catch(() => setData(null))
            .finally(() => setLoading(false))
          observer.disconnect()
        }
      },
      { rootMargin: '400px' },
    )
    observer.observe(ref)
    return () => observer.disconnect()
  }, [ref, slug, productId, scope])

  return { setRef, data, loading }
}

/** Один вызов POST .../view при открытии товара, с защитой от двойного вызова в StrictMode. */
export function useTrackProductView(slug: string, productId: string, ready: boolean) {
  const tracked = useRef<string | null>(null)
  useEffect(() => {
    if (!ready) return
    const key = `${slug}:${productId}`
    if (tracked.current === key) return
    tracked.current = key
    trackProductView(slug, Number(productId))
  }, [slug, productId, ready])
}
