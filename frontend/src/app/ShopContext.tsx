import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { getShop } from '../entities/profile/api'

interface ShopState {
  shopName: string
  setShopName: (name: string) => void
}

const ShopContext = createContext<ShopState | null>(null)

export function ShopProvider({ children }: { children: ReactNode }) {
  const [shopName, setShopName] = useState('WaySklad')

  useEffect(() => {
    getShop()
      .then((s) => setShopName(s.name))
      .catch(() => {})
  }, [])

  return <ShopContext.Provider value={{ shopName, setShopName }}>{children}</ShopContext.Provider>
}

export function useShop(): ShopState {
  const ctx = useContext(ShopContext)
  if (!ctx) throw new Error('useShop должен использоваться внутри ShopProvider')
  return ctx
}
