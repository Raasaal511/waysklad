import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './app/AuthContext'
import { ThemeProvider } from './app/ThemeContext'
import { ShopProvider } from './app/ShopContext'
import { CatalogProvider } from './app/CatalogContext'
import { OnboardingProvider } from './app/OnboardingContext'
import { OnboardingOverlay } from './app/OnboardingOverlay'
import { RequireAuth } from './app/RequireAuth'
import { AppLayout } from './app/AppLayout'
import { LoginPage } from './pages/auth/LoginPage'
import { SalePage } from './pages/sales/SalePage'
import { SaleNewPage } from './pages/sales/SaleNewPage'
import { SaleDetailPage } from './pages/sales/SaleDetailPage'
import { ProductsPage } from './pages/products/ProductsPage'
import { ProductDetailPage } from './pages/products/ProductDetailPage'
import { ProductNewPage } from './pages/products/ProductNewPage'
import { ProductEditPage } from './pages/products/ProductEditPage'
import { StockPage } from './pages/stock/StockPage'
import { WarehouseDetailPage } from './pages/stock/WarehouseDetailPage'
import { WarehouseMovementPage } from './pages/stock/WarehouseMovementPage'
import { MovementHistoryPage } from './pages/stock/MovementHistoryPage'
import { OrdersPage } from './pages/orders/OrdersPage'
import { OrderNewPage } from './pages/orders/OrderNewPage'
import { OrderDetailPage } from './pages/orders/OrderDetailPage'
import { StorefrontRequestsPage } from './pages/storefront/StorefrontRequestsPage'
import { StorefrontManagePage } from './pages/storefront/StorefrontManagePage'
import { StorefrontCatalogPage } from './pages/storefront/StorefrontCatalogPage'
import { StorefrontProductPage } from './pages/storefront/StorefrontProductPage'
import { StorefrontCartPage } from './pages/storefront/StorefrontCartPage'
import { StorefrontRequestPage } from './pages/storefront/StorefrontRequestPage'
import { StorefrontMyOrdersPage } from './pages/storefront/StorefrontMyOrdersPage'
import { MarketplacePage } from './pages/marketplace/MarketplacePage'
import { MarketplaceShopsPage } from './pages/marketplace/MarketplaceShopsPage'
import { PublicLayout } from './widgets/public-header/PublicLayout'
import { TasksPage } from './pages/tasks/TasksPage'
import { DebtsPage } from './pages/debts/DebtsPage'
import { DebtNewPage } from './pages/debts/DebtNewPage'
import { DebtDetailPage } from './pages/debts/DebtDetailPage'
import { ClientsPage } from './pages/clients/ClientsPage'
import { ClientDetailPage } from './pages/clients/ClientDetailPage'
import { AnalyticsPage } from './pages/analytics/AnalyticsPage'
import { ProfilePage } from './pages/profile/ProfilePage'
import { EmployeesPage } from './pages/employees/EmployeesPage'
import { AdminPage } from './pages/admin/AdminPage'

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/admin/*" element={<AdminPage />} />
            <Route
              path="/marketplace"
              element={
                <PublicLayout>
                  <MarketplacePage />
                </PublicLayout>
              }
            />
            <Route
              path="/marketplace/shops"
              element={
                <PublicLayout>
                  <MarketplaceShopsPage />
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
              <Route path="/orders/storefront-requests" element={<StorefrontRequestsPage />} />
              <Route path="/orders/:id" element={<OrderDetailPage />} />
              <Route path="/storefront" element={<StorefrontManagePage />} />
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
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}
