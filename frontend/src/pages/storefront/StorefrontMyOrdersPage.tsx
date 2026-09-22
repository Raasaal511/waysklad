import { Navigate, useParams } from 'react-router-dom'

/** Старый URL — редирект в профиль. Логика заказов живёт в CustomerAccountPage. */
export function StorefrontMyOrdersPage() {
  const { slug = '' } = useParams<{ slug: string }>()
  return <Navigate to={`/store/${slug}/account/orders`} replace />
}
