import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { IconChevronLeft } from '@tabler/icons-react'
import { getProduct, type Product } from '../../entities/product/api'
import { useAuth } from '../../app/AuthContext'
import { useCatalog } from '../../app/CatalogContext'
import { ApiError } from '../../shared/api/client'
import { ProductForm } from './ProductForm'
import layoutStyles from '../../shared/ui/Layout.module.css'

export function ProductEditPage() {
  const { id } = useParams<{ id: string }>()
  const productId = Number(id)
  const { user } = useAuth()
  const canManage = user?.role === 'owner' || user?.role === 'manager'
  const navigate = useNavigate()
  const {
    categories,
    units,
    warehouses,
    ensureCategories,
    ensureUnits,
    ensureWarehouses,
    refresh,
  } = useCatalog()

  const [product, setProduct] = useState<Product | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    ensureCategories().catch(() => {})
    ensureUnits().catch(() => {})
    ensureWarehouses().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!Number.isFinite(productId) || productId <= 0) {
      setProduct(null)
      setError('Товар не найден')
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    getProduct(productId)
      .then((p) => {
        if (!cancelled) setProduct(p)
      })
      .catch((err) => {
        if (cancelled) return
        setProduct(null)
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить товар')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [productId])

  if (!canManage) {
    return <Navigate to={Number.isFinite(productId) ? `/products/${productId}` : '/products'} replace />
  }

  const backTo = Number.isFinite(productId) && productId > 0 ? `/products/${productId}` : '/products'

  return (
    <div className={layoutStyles.stack}>
      <Link to={backTo} className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> К карточке товара
      </Link>

      {loading ? (
        <p className={layoutStyles.textMuted}>Загрузка…</p>
      ) : !product ? (
        <p className={layoutStyles.error}>{error ?? 'Товар не найден'}</p>
      ) : (
        <ProductForm
          key={product.id}
          product={product}
          categories={categories}
          units={units}
          warehouses={warehouses}
          onCategoriesChanged={() => refresh(['categories'])}
          onUnitsChanged={() => refresh(['units'])}
          onWarehousesChanged={() => refresh(['warehouses'])}
          onDone={(saved) => {
            refresh(['products', 'stock']).catch(() => {})
            navigate(`/products/${saved?.id ?? product.id}`, { replace: true })
          }}
        />
      )}
    </div>
  )
}
