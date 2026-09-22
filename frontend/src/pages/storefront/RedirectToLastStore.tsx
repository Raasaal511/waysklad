import { Navigate } from 'react-router-dom'
import { loadLastStoreSlug } from '../../shared/lib/lastStore'

/**
 * Старые глобальные ссылки (/favorites, /cart, /account) без магазина в URL.
 * Есть последний магазин в localStorage → туда; нет → вход владельца /login
 * (общей точки входа покупателя без магазина больше нет).
 */
export function RedirectToLastStore({ suffix }: { suffix: string }) {
  const slug = loadLastStoreSlug()
  if (slug) {
    return <Navigate to={`/store/${slug}${suffix}`} replace />
  }
  return <Navigate to="/login" replace />
}
