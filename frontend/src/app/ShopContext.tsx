import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { getShop, type Tenant } from '../entities/profile/api'

interface ShopState {
  shopName: string
  setShopName: (name: string) => void
  /** Полный объект магазина (настройки Telegram-сводки и т.п.) — null, пока не
   * загружен впервые. Вкладки профиля читают отсюда вместо своего getShop(),
   * чтобы не дублировать запрос, уже сделанный при старте приложения. */
  shop: Tenant | null
  setShop: (shop: Tenant) => void
  refreshShop: () => Promise<Tenant | null>
}

const ShopContext = createContext<ShopState | null>(null)

export function ShopProvider({ children }: { children: ReactNode }) {
  const [shopName, setShopName] = useState('WaySklad')
  const [shop, setShop] = useState<Tenant | null>(null)

  async function refreshShop() {
    try {
      const s = await getShop()
      setShop(s)
      setShopName(s.name)
      return s
    } catch {
      return null
    }
  }

  useEffect(() => {
    refreshShop()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <ShopContext.Provider value={{ shopName, setShopName, shop, setShop, refreshShop }}>
      {children}
    </ShopContext.Provider>
  )
}

export function useShop(): ShopState {
  const ctx = useContext(ShopContext)
  if (!ctx) throw new Error('useShop должен использоваться внутри ShopProvider')
  return ctx
}
