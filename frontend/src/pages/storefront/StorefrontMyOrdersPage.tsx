import { Navigate } from 'react-router-dom'

/** Старый URL — редирект в общий профиль. */
export function StorefrontMyOrdersPage() {
  return <Navigate to="/account/orders" replace />
}
