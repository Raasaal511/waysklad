import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './app/AuthContext'
import { RequireAuth } from './app/RequireAuth'
import { AppLayout } from './app/AppLayout'
import { LoginPage } from './pages/auth/LoginPage'
import { SalePage } from './pages/sales/SalePage'
import { ProductsPage } from './pages/products/ProductsPage'
import { StockPage } from './pages/stock/StockPage'
import { OrdersPage } from './pages/orders/OrdersPage'
import { DebtsPage } from './pages/debts/DebtsPage'
import { ClientsPage } from './pages/clients/ClientsPage'
import { AnalyticsPage } from './pages/analytics/AnalyticsPage'

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <AppLayout />
              </RequireAuth>
            }
          >
            <Route path="/" element={<SalePage />} />
            <Route path="/products" element={<ProductsPage />} />
            <Route path="/stock" element={<StockPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/debts" element={<DebtsPage />} />
            <Route path="/clients" element={<ClientsPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
