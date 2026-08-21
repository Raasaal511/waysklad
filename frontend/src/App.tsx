import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './app/AuthContext'
import { ThemeProvider } from './app/ThemeContext'
import { ShopProvider } from './app/ShopContext'
import { RequireAuth } from './app/RequireAuth'
import { AppLayout } from './app/AppLayout'
import { LoginPage } from './pages/auth/LoginPage'
import { SalePage } from './pages/sales/SalePage'
import { ProductsPage } from './pages/products/ProductsPage'
import { StockPage } from './pages/stock/StockPage'
import { WarehouseDetailPage } from './pages/stock/WarehouseDetailPage'
import { MovementHistoryPage } from './pages/stock/MovementHistoryPage'
import { OrdersPage } from './pages/orders/OrdersPage'
import { TasksPage } from './pages/tasks/TasksPage'
import { DebtsPage } from './pages/debts/DebtsPage'
import { DebtDetailPage } from './pages/debts/DebtDetailPage'
import { ClientsPage } from './pages/clients/ClientsPage'
import { AnalyticsPage } from './pages/analytics/AnalyticsPage'
import { ProfilePage } from './pages/profile/ProfilePage'
import { EmployeesPage } from './pages/employees/EmployeesPage'
import { AuditPage } from './pages/audit/AuditPage'

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              element={
                <RequireAuth>
                  <ShopProvider>
                    <AppLayout />
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
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/debts" element={<DebtsPage />} />
              <Route path="/debts/:id" element={<DebtDetailPage />} />
              <Route path="/clients" element={<ClientsPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/employees" element={<EmployeesPage />} />
              <Route path="/audit" element={<AuditPage />} />
              <Route path="/profile" element={<ProfilePage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}
