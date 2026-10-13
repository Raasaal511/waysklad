import { Suspense, lazy } from 'react'
import { BrowserRouter, Navigate, Routes, Route, useLocation } from 'react-router-dom'
import { AuthProvider } from './app/AuthContext'
import { ThemeProvider } from './app/ThemeContext'
import { ShopProvider } from './app/ShopContext'
import { CatalogProvider } from './app/CatalogContext'
import { OnboardingProvider } from './app/OnboardingContext'
import { OnboardingOverlay } from './app/OnboardingOverlay'
import { RequireAuth } from './app/RequireAuth'
import { RequireFeature } from './app/RequireFeature'
import { AppLayout } from './app/AppLayout'
import { LoginPage } from './pages/auth/LoginPage'
import { PrivacyPage } from './pages/auth/PrivacyPage'
import { StorefrontRequestPage } from './pages/storefront/StorefrontRequestPage'
import { CustomerAccountPage } from './pages/storefront/CustomerAccountPage'
import { CustomerChatPage } from './pages/storefront/CustomerChatPage'
import { StorefrontCatalogPage } from './pages/storefront/StorefrontCatalogPage'
import { StorefrontProductPage } from './pages/storefront/StorefrontProductPage'
import { StorefrontCartPage } from './pages/storefront/StorefrontCartPage'
import { CustomerAuthPage } from './pages/storefront/CustomerAuthPage'
import { FavoritesPage } from './pages/storefront/FavoritesPage'
import { PublicNotFoundPage } from './pages/storefront/PublicNotFoundPage'
import { RedirectToLastStore } from './pages/storefront/RedirectToLastStore'
import { PublicLayout } from './widgets/public-header/PublicLayout'
import { CabinetNotFoundPage } from './pages/CabinetNotFoundPage'
import { ServiceWorkerNavigation } from './app/ServiceWorkerNavigation'

// Кабинет владельца и админка не нужны покупателю на публичных страницах —
// вынесены в отдельные чанки, чтобы публичные страницы (/store/*) не тянули их JS первой загрузкой (P7 п.2).
const SalePage = lazy(() => import('./pages/sales/SalePage').then((m) => ({ default: m.SalePage })))
const SaleNewPage = lazy(() => import('./pages/sales/SaleNewPage').then((m) => ({ default: m.SaleNewPage })))
const SaleDetailPage = lazy(() =>
  import('./pages/sales/SaleDetailPage').then((m) => ({ default: m.SaleDetailPage })),
)
const ProductsPage = lazy(() =>
  import('./pages/products/ProductsPage').then((m) => ({ default: m.ProductsPage })),
)
const ProductDetailPage = lazy(() =>
  import('./pages/products/ProductDetailPage').then((m) => ({ default: m.ProductDetailPage })),
)
const ProductNewPage = lazy(() =>
  import('./pages/products/ProductNewPage').then((m) => ({ default: m.ProductNewPage })),
)
const ProductEditPage = lazy(() =>
  import('./pages/products/ProductEditPage').then((m) => ({ default: m.ProductEditPage })),
)
const ServicesPage = lazy(() =>
  import('./pages/services/ServicesPage').then((m) => ({ default: m.ServicesPage })),
)
const ServiceEditorPage = lazy(() =>
  import('./pages/services/ServiceEditorPage').then((m) => ({ default: m.ServiceEditorPage })),
)
const StockPage = lazy(() => import('./pages/stock/StockPage').then((m) => ({ default: m.StockPage })))
const WarehouseDetailPage = lazy(() =>
  import('./pages/stock/WarehouseDetailPage').then((m) => ({ default: m.WarehouseDetailPage })),
)
const WarehouseMovementPage = lazy(() =>
  import('./pages/stock/WarehouseMovementPage').then((m) => ({ default: m.WarehouseMovementPage })),
)
const MovementHistoryPage = lazy(() =>
  import('./pages/stock/MovementHistoryPage').then((m) => ({ default: m.MovementHistoryPage })),
)
const OrdersPage = lazy(() => import('./pages/orders/OrdersPage').then((m) => ({ default: m.OrdersPage })))
const OrderNewPage = lazy(() =>
  import('./pages/orders/OrderNewPage').then((m) => ({ default: m.OrderNewPage })),
)
const OrderDetailPage = lazy(() =>
  import('./pages/orders/OrderDetailPage').then((m) => ({ default: m.OrderDetailPage })),
)
const StorefrontRequestsPage = lazy(() =>
  import('./pages/storefront/StorefrontRequestsPage').then((m) => ({ default: m.StorefrontRequestsPage })),
)
const StorefrontManagePage = lazy(() =>
  import('./pages/storefront/StorefrontManagePage').then((m) => ({ default: m.StorefrontManagePage })),
)
const TasksPage = lazy(() => import('./pages/tasks/TasksPage').then((m) => ({ default: m.TasksPage })))
const DebtsPage = lazy(() => import('./pages/debts/DebtsPage').then((m) => ({ default: m.DebtsPage })))
const DebtNewPage = lazy(() => import('./pages/debts/DebtNewPage').then((m) => ({ default: m.DebtNewPage })))
const DebtDetailPage = lazy(() =>
  import('./pages/debts/DebtDetailPage').then((m) => ({ default: m.DebtDetailPage })),
)
const ClientsPage = lazy(() => import('./pages/clients/ClientsPage').then((m) => ({ default: m.ClientsPage })))
const ClientDetailPage = lazy(() =>
  import('./pages/clients/ClientDetailPage').then((m) => ({ default: m.ClientDetailPage })),
)
const AnalyticsPage = lazy(() =>
  import('./pages/analytics/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage })),
)
const ProfilePage = lazy(() => import('./pages/profile/ProfilePage').then((m) => ({ default: m.ProfilePage })))
const EmployeesPage = lazy(() =>
  import('./pages/employees/EmployeesPage').then((m) => ({ default: m.EmployeesPage })),
)
const AdminPage = lazy(() => import('./pages/admin/AdminPage').then((m) => ({ default: m.AdminPage })))

function RedirectMyOrdersToAccount() {
  return <Navigate to="/account/orders" replace />
}

function RedirectStoreAccountToGlobal() {
  const location = useLocation()
  const rest = location.pathname.replace(/^\/store\/[^/]+\/account/, '') || ''
  return <Navigate to={`/account${rest}${location.search}${location.hash}`} replace />
}

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <ServiceWorkerNavigation />
          <Suspense fallback={null}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/privacy" element={<PrivacyPage />} />
              <Route path="/admin/*" element={<AdminPage />} />
              {/* Старые глобальные URL: без магазина в контексте — к последнему
                  магазину или на /login. Маркетплейс для покупателя закрыт. */}
              <Route path="/cart" element={<RedirectToLastStore suffix="/cart" />} />
              <Route path="/favorites" element={<RedirectToLastStore suffix="/favorites" />} />
              <Route
                path="/account"
                element={
                  <PublicLayout>
                    <CustomerAccountPage />
                  </PublicLayout>
                }
              />
              <Route
                path="/account/orders"
                element={
                  <PublicLayout>
                    <CustomerAccountPage />
                  </PublicLayout>
                }
              />
              <Route
                path="/account/chats"
                element={
                  <PublicLayout>
                    <CustomerAccountPage />
                  </PublicLayout>
                }
              />
              <Route
                path="/account/chats/:requestId"
                element={
                  <PublicLayout>
                    <CustomerChatPage />
                  </PublicLayout>
                }
              />
              <Route
                path="/account/reviews"
                element={
                  <PublicLayout>
                    <CustomerAccountPage />
                  </PublicLayout>
                }
              />
              <Route
                path="/account/shops"
                element={
                  <PublicLayout>
                    <CustomerAccountPage />
                  </PublicLayout>
                }
              />
              {/* неизвестный адрес витрины или кабинета покупателя — публичная «не найдено»,
                  а не вход владельца (ловушка * ниже — только для кабинета) */}
              {['/store/:slug/*', '/account/*'].map((path) => (
                <Route
                  key={path}
                  path={path}
                  element={
                    <PublicLayout>
                      <PublicNotFoundPage />
                    </PublicLayout>
                  }
                />
              ))}
              <Route
                path="/marketplace/*"
                element={
                  <PublicLayout>
                    <PublicNotFoundPage />
                  </PublicLayout>
                }
              />
              <Route
                path="/store/:slug"
                element={
                  <PublicLayout>
                    <StorefrontCatalogPage />
                  </PublicLayout>
                }
              />
              <Route
                path="/store/:slug/products/:productId"
                element={
                  <PublicLayout>
                    <StorefrontProductPage />
                  </PublicLayout>
                }
              />
              <Route
                path="/store/:slug/cart"
                element={
                  <PublicLayout>
                    <StorefrontCartPage />
                  </PublicLayout>
                }
              />
              <Route
                path="/store/:slug/favorites"
                element={
                  <PublicLayout>
                    <FavoritesPage />
                  </PublicLayout>
                }
              />
              <Route path="/store/:slug/account/*" element={<RedirectStoreAccountToGlobal />} />
              <Route path="/store/:slug/account" element={<RedirectStoreAccountToGlobal />} />
              <Route
                path="/store/:slug/login"
                element={
                  <PublicLayout>
                    <CustomerAuthPage />
                  </PublicLayout>
                }
              />
              <Route
                path="/store/:slug/request"
                element={
                  <PublicLayout>
                    <StorefrontRequestPage />
                  </PublicLayout>
                }
              />
              <Route path="/store/:slug/my-orders" element={<RedirectMyOrdersToAccount />} />
              <Route
                element={
                  <RequireAuth>
                    <ShopProvider>
                      <CatalogProvider>
                        <OnboardingProvider>
                          <AppLayout />
                          <OnboardingOverlay />
                        </OnboardingProvider>
                      </CatalogProvider>
                    </ShopProvider>
                  </RequireAuth>
                }
              >
                <Route path="/" element={<SalePage />} />
                <Route path="/sales/new" element={<SaleNewPage />} />
                <Route path="/sales/:id" element={<SaleDetailPage />} />
                <Route path="/products" element={<ProductsPage />} />
                <Route path="/products/new" element={<ProductNewPage />} />
                <Route path="/products/:id/edit" element={<ProductEditPage />} />
                <Route path="/products/:id" element={<ProductDetailPage />} />
                <Route path="/services" element={<ServicesPage />} />
                <Route path="/services/new" element={<ServiceEditorPage />} />
                <Route path="/services/:id" element={<ServiceEditorPage />} />
                <Route path="/stock" element={<StockPage />} />
                <Route path="/stock/history" element={<MovementHistoryPage />} />
                <Route path="/stock/:id/movement/:mode" element={<WarehouseMovementPage />} />
                <Route path="/stock/:id" element={<WarehouseDetailPage />} />
                <Route path="/orders" element={<OrdersPage />} />
                <Route path="/orders/new" element={<OrderNewPage />} />
                <Route
                  path="/orders/storefront-requests"
                  element={
                    <RequireFeature feature="storefront">
                      <StorefrontRequestsPage />
                    </RequireFeature>
                  }
                />
                <Route path="/orders/:id" element={<OrderDetailPage />} />
                <Route
                  path="/storefront"
                  element={
                    <RequireFeature feature="storefront">
                      <StorefrontManagePage />
                    </RequireFeature>
                  }
                />
                <Route path="/tasks" element={<TasksPage />} />
                <Route path="/debts" element={<DebtsPage />} />
                <Route path="/debts/new" element={<DebtNewPage />} />
                <Route path="/debts/:id" element={<DebtDetailPage />} />
                <Route path="/clients" element={<ClientsPage />} />
                <Route path="/clients/:id" element={<ClientDetailPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/employees" element={<EmployeesPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                {/* неизвестный адрес: сотрудник видит «Такой страницы нет», гость — вход */}
                <Route path="*" element={<CabinetNotFoundPage />} />
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}
