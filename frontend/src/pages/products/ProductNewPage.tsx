import { useEffect } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { IconChevronLeft } from '@tabler/icons-react'
import { useAuth } from '../../app/AuthContext'
import { useCatalog } from '../../app/CatalogContext'
import { ProductForm } from './ProductForm'
import layoutStyles from '../../shared/ui/Layout.module.css'

export function ProductNewPage() {
  const { user } = useAuth()
  const canManage = user?.role === 'owner' || user?.role === 'manager'
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const isService = searchParams.get('kind') === 'service'
  const listHref = isService ? '/products?kind=service' : '/products'
  const {
    categories,
    units,
    warehouses,
    ensureCategories,
    ensureUnits,
    ensureWarehouses,
    refresh,
  } = useCatalog()

  useEffect(() => {
    ensureCategories().catch(() => {})
    ensureUnits().catch(() => {})
    ensureWarehouses().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!canManage) {
    return <Navigate to="/products" replace />
  }

  return (
    <div className={layoutStyles.stack}>
      <Link to={listHref} className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> {isService ? 'Все услуги' : 'Все товары'}
      </Link>
      <ProductForm
        product={null}
        kind={isService ? 'service' : 'product'}
        categories={categories}
        units={units}
        warehouses={warehouses}
        onCategoriesChanged={() => refresh(['categories'])}
        onUnitsChanged={() => refresh(['units'])}
        onWarehousesChanged={() => refresh(['warehouses'])}
        onDone={(saved) => {
          refresh(['products', 'stock']).catch(() => {})
          navigate(saved ? `/products/${saved.id}` : listHref, { replace: true })
        }}
      />
    </div>
  )
}
