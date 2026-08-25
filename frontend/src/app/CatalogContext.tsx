import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'
import { listWarehouses, listStock, type Warehouse, type StockItem } from '../entities/inventory/api'
import { listAllProducts, listUnits, listCategories, type Product, type Unit, type Category } from '../entities/product/api'
import { listEmployees } from '../entities/profile/api'
import type { User } from '../entities/auth/api'

type CatalogKey = 'products' | 'warehouses' | 'units' | 'categories' | 'stock' | 'employees'

interface CatalogState {
  products: Product[]
  warehouses: Warehouse[]
  units: Unit[]
  categories: Category[]
  stock: StockItem[]
  employees: User[]
}

interface CatalogContextValue extends CatalogState {
  ensureProducts: () => Promise<Product[]>
  ensureWarehouses: () => Promise<Warehouse[]>
  ensureUnits: () => Promise<Unit[]>
  ensureCategories: () => Promise<Category[]>
  ensureStock: () => Promise<StockItem[]>
  ensureEmployees: () => Promise<User[]>
  refresh: (keys?: CatalogKey[]) => Promise<void>
}

const CatalogContext = createContext<CatalogContextValue | null>(null)

const LOADERS: Record<CatalogKey, () => Promise<unknown>> = {
  products: () => listAllProducts(),
  warehouses: () => listWarehouses(),
  units: () => listUnits(),
  categories: () => listCategories(),
  stock: () => listStock(),
  employees: () => listEmployees(),
}

export function CatalogProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<CatalogState>({
    products: [],
    warehouses: [],
    units: [],
    categories: [],
    stock: [],
    employees: [],
  })
  const stateRef = useRef(state)
  stateRef.current = state
  const inflight = useRef<Partial<Record<CatalogKey, Promise<unknown>>>>({})
  const loaded = useRef<Partial<Record<CatalogKey, boolean>>>({})

  const ensure = useCallback(<K extends CatalogKey>(key: K): Promise<CatalogState[K]> => {
    if (loaded.current[key]) return Promise.resolve(stateRef.current[key]) as Promise<CatalogState[K]>
    if (inflight.current[key]) return inflight.current[key] as Promise<CatalogState[K]>
    const promise = LOADERS[key]()
      .then((data) => {
        loaded.current[key] = true
        setState((prev) => ({ ...prev, [key]: data }))
        return data
      })
      .finally(() => {
        delete inflight.current[key]
      })
    inflight.current[key] = promise
    return promise as Promise<CatalogState[K]>
  }, [])

  const refresh = useCallback(async (keys?: CatalogKey[]) => {
    const targets = keys ?? (Object.keys(LOADERS) as CatalogKey[])
    for (const key of targets) {
      delete loaded.current[key]
    }
    await Promise.all(targets.map((key) => ensure(key)))
  }, [ensure])

  const value: CatalogContextValue = {
    ...state,
    ensureProducts: () => ensure('products'),
    ensureWarehouses: () => ensure('warehouses'),
    ensureUnits: () => ensure('units'),
    ensureCategories: () => ensure('categories'),
    ensureStock: () => ensure('stock'),
    ensureEmployees: () => ensure('employees'),
    refresh,
  }

  return <CatalogContext.Provider value={value}>{children}</CatalogContext.Provider>
}

export function useCatalog(): CatalogContextValue {
  const ctx = useContext(CatalogContext)
  if (!ctx) throw new Error('useCatalog должен использоваться внутри CatalogProvider')
  return ctx
}
