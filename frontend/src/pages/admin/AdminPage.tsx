import { useCallback, useState } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AdminLayout, type AdminPeriod } from './AdminLayout'
import { AdminLogin } from './AdminLogin'
import { useAdminAuth } from './shared'
import { OverviewSection } from './sections/OverviewSection'
import { TenantsSection } from './sections/TenantsSection'
import { TenantDetailSection } from './sections/TenantDetailSection'
import { ServerSection } from './sections/ServerSection'
import { ErrorsSection } from './sections/ErrorsSection'
import { FeedbackSection } from './sections/FeedbackSection'

/** Заголовок раздела по текущему пути — шапка каркаса показывает его в H1. */
function sectionTitle(pathname: string): string {
  if (pathname.startsWith('/admin/tenants/')) return 'Магазин'
  if (pathname.startsWith('/admin/tenants')) return 'Магазины'
  if (pathname.startsWith('/admin/server')) return 'Сервер'
  if (pathname.startsWith('/admin/errors')) return 'Ошибки'
  if (pathname.startsWith('/admin/feedback')) return 'Обратная связь'
  return 'Обзор'
}

/** Переключатель периода нужен не везде: на карточке магазина он не применим. */
function usesPeriod(pathname: string): boolean {
  return pathname.startsWith('/admin/errors') || pathname === '/admin'
}

export function AdminPage() {
  const auth = useAdminAuth()
  const location = useLocation()

  const [period, setPeriod] = useState<AdminPeriod>('24h')
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  // счётчик, по изменению которого разделы перезагружают данные: так кнопка
  // «обновить» в общей шапке работает с любым разделом, не зная про его состояние
  const [refreshKey, setRefreshKey] = useState(0)

  const refresh = useCallback(() => {
    setRefreshing(true)
    setRefreshKey((key) => key + 1)
  }, [])

  const onLoaded = useCallback(() => {
    setUpdatedAt(new Date())
    setRefreshing(false)
  }, [])

  if (!auth.token) {
    return <AdminLogin onSuccess={auth.login} />
  }

  const sectionProps = { logout: auth.logout, refreshKey, onLoaded }

  return (
    <AdminLayout
      title={sectionTitle(location.pathname)}
      onLogout={auth.logout}
      updatedAt={updatedAt}
      onRefresh={refresh}
      refreshing={refreshing}
      period={usesPeriod(location.pathname) ? period : undefined}
      onPeriodChange={usesPeriod(location.pathname) ? setPeriod : undefined}
    >
      <Routes>
        <Route index element={<OverviewSection {...sectionProps} period={period} />} />
        <Route path="tenants" element={<TenantsSection {...sectionProps} />} />
        <Route path="tenants/:id" element={<TenantDetailSection {...sectionProps} />} />
        <Route path="server" element={<ServerSection {...sectionProps} />} />
        <Route path="errors" element={<ErrorsSection {...sectionProps} />} />
        <Route path="feedback" element={<FeedbackSection {...sectionProps} />} />
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </AdminLayout>
  )
}
