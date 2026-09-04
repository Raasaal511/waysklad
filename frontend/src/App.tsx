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
import { ProductsPage } from './pages/products/ProductsPage'
import { StockPage } from './pages/stock/StockPage'
import { WarehouseDetailPage } from './pages/stock/WarehouseDetailPage'
import { MovementHistoryPage } from './pages/stock/MovementHistoryPage'
import { OrdersPage } from './pages/orders/OrdersPage'
import { StorefrontRequestsPage } from './pages/storefront/StorefrontRequestsPage'
import { StorefrontManagePage } from './pages/storefront/StorefrontManagePage'
import { StorefrontCatalogPage } from './pages/storefront/StorefrontCatalogPage'
import { StorefrontProductPage } from './pages/storefront/StorefrontProductPage'
import { StorefrontCartPage } from './pages/storefront/StorefrontCartPage'
import { StorefrontRequestPage } from './pages/storefront/StorefrontRequestPage'
import { TasksPage } from './pages/tasks/TasksPage'
import { DebtsPage } from './pages/debts/DebtsPage'
import { DebtDetailPage } from './pages/debts/DebtDetailPage'
import { ClientsPage } from './pages/clients/ClientsPage'
import { ClientDetailPage } from './pages/clients/ClientDetailPage'
import { AnalyticsPage } from './pages/analytics/AnalyticsPage'
import { ProfilePage } from './pages/profile/ProfilePage'
import { EmployeesPage } from './pages/employees/EmployeesPage'

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/store/:slug" element={<StorefrontCatalogPage />} />
            <Route path="/store/:slug/products/:productId" element={<StorefrontProductPage />} />
            <Route path="/store/:slug/cart" element={<StorefrontCartPage />} />
            <Route path="/store/:slug/request" element={<StorefrontRequestPage />} />
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
              <Route path="/products" element={<ProductsPage />} />
              <Route path="/stock" element={<StockPage />} />
              <Route path="/stock/history" element={<MovementHistoryPage />} />
              <Route path="/stock/:id" element={<WarehouseDetailPage />} />
              <Route path="/orders" element={<OrdersPage />} />
              <Route path="/orders/storefront-requests" element={<StorefrontRequestsPage />} />
              <Route path="/storefront" element={<StorefrontManagePage />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/debts" element={<DebtsPage />} />
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
