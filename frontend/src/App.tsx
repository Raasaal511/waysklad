import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
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
import { StorefrontRequestPage } from './pages/storefront/StorefrontRequestPage'
import { StorefrontMyOrdersPage } from './pages/storefront/StorefrontMyOrdersPage'
import { StorefrontCatalogPage } from './pages/storefront/StorefrontCatalogPage'
import { StorefrontProductPage } from './pages/storefront/StorefrontProductPage'
import { StorefrontCartPage } from './pages/storefront/StorefrontCartPage'
import { CustomerAuthPage } from './pages/storefront/CustomerAuthPage'
import { MarketplaceComingSoonPage } from './pages/marketplace/MarketplaceComingSoonPage'
import { PublicLayout } from './widgets/public-header/PublicLayout'

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

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Suspense fallback={null}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/admin/*" element={<AdminPage />} />
              {/* Маркетплейс (общая витрина всех магазинов) отключён: backend отдаёт
                  404 на /api/marketplace/*, ссылок в интерфейсе нет. Роут оставлен
                  заглушкой — по старым ссылкам должна открываться внятная страница,
                  а не белый экран. Готовые страницы лежат рядом, см.
                  MarketplaceComingSoonPage. */}
              <Route
                path="/marketplace/*"
                element={
                  <PublicLayout>
                    <MarketplaceComingSoonPage />
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
                path="/store/:slug/login"
                element={
                  <PublicLayout>
                    <CustomerAuthPage />
                  </PublicLayout>
                }
              />
              <Route path="/store/:slug/request" element={<StorefrontRequestPage />} />
              <Route path="/store/:slug/my-orders" element={<StorefrontMyOrdersPage />} />
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
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}
