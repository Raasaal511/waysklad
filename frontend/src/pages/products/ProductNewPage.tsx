import { useEffect } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { IconChevronLeft } from '@tabler/icons-react'
import { useAuth } from '../../app/AuthContext'
import { useCatalog } from '../../app/CatalogContext'
import { ProductForm } from './ProductForm'
import layoutStyles from '../../shared/ui/Layout.module.css'

export function ProductNewPage() {
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
      <Link to="/products" className={layoutStyles.backLink}>
        <IconChevronLeft size={16} stroke={1.8} /> Все товары
      </Link>
      <ProductForm
        product={null}
        categories={categories}
        units={units}
        warehouses={warehouses}
        onCategoriesChanged={() => refresh(['categories'])}
        onUnitsChanged={() => refresh(['units'])}
        onWarehousesChanged={() => refresh(['warehouses'])}
        onDone={(saved) => {
          refresh(['products', 'stock']).catch(() => {})
          navigate(saved ? `/products/${saved.id}` : '/products', { replace: true })
        }}
      />
    </div>
  )
}
