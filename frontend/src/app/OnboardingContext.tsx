import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCatalog } from './CatalogContext'
import { useAuth } from './AuthContext'

export interface OnboardingStep {
  id: string
  title: string
  body: string
  /** DOM-якорь для подсветки — совпадает с data-onboarding у элемента.
   * null — шаг без подсветки (приветствие/финал), рисуется по центру. */
  target: string | null
  /** Куда перейти при показе шага, если пользователь не там сам. */
  to?: string
  /** true, если шаг завершается автоматически по факту действия (не кнопкой). */
  auto?: boolean
}

const STEPS: OnboardingStep[] = [
  {
    id: 'warehouses',
    title: 'Быстро настроим магазин: начнём со склада',
    body: 'Пройдём вместе: склад → товар → первая продажа → кому назначить продавца → где смотреть выручку. Займёт пару минут. Склад — место, где реально лежит товар. Без него некуда принять товар и не с чего продавать.',
    target: '/stock',
    to: '/stock',
    auto: true,
  },
  {
    id: 'products',
    title: 'Добавьте первый товар',
    body: 'Название и цена — обязательны, остальное можно заполнить потом.',
    target: '/products',
    to: '/products',
    auto: true,
  },
  {
    id: 'sale',
    title: 'Оформите первую продажу',
    body: 'Можно принять оплату сразу (наличные/перевод) или отпустить товар в долг — тогда он появится в разделе «Долги».',
    target: '/',
    to: '/',
  },
  {
    id: 'debts',
    title: 'Долги клиентов — здесь',
    body: 'Если продали в долг — весь список должников и сроков оплаты в этом разделе.',
    target: '/debts',
    to: '/debts',
  },
  {
    id: 'employees',
    title: 'Пригласите продавца',
    body: 'Заведите отдельный вход для сотрудника — у него будут только нужные ему права, без доступа к настройкам магазина.',
    target: '/employees',
    to: '/employees',
  },
  {
    id: 'analytics',
    title: 'Выручка и прибыль — здесь',
    body: 'Динамика продаж, топ товаров, что залежалось на складе. Загляните сюда после нескольких продаж.',
    target: '/analytics',
    to: '/analytics',
  },
]

interface OnboardingState {
  active: boolean
  stepIndex: number
  step: OnboardingStep | null
  totalSteps: number
  start: () => void
  next: () => void
  skip: () => void
}

const OnboardingContext = createContext<OnboardingState | null>(null)

function storageKey(userId: number | undefined) {
  return `waysklad:onboarding-done:${userId ?? 'unknown'}`
}

export function OnboardingProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const { warehouses, products, ensureWarehouses, ensureProducts } = useCatalog()
  const navigate = useNavigate()
  const [active, setActive] = useState(false)
  const [stepIndex, setStepIndex] = useState(0)

  const key = storageKey(user?.id)

  useEffect(() => {
    if (user?.role !== 'owner') return
    if (localStorage.getItem(key) === '1') return
    if (sessionStorage.getItem('waysklad:onboarding-pending') !== '1') return
    setActive(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.role])

  useEffect(() => {
    if (!active) return
    ensureWarehouses().catch(() => {})
    ensureProducts().catch(() => {})
  }, [active, ensureWarehouses, ensureProducts])

  const step = active ? STEPS[stepIndex] ?? null : null

  useEffect(() => {
    if (!active || !step?.to) return
    navigate(step.to)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, stepIndex])

  // авто-продвижение по факту действия — без клика "Далее"
  useEffect(() => {
    if (!active || !step?.auto) return
    if (step.id === 'warehouses' && warehouses.length > 0) next()
    if (step.id === 'products' && products.length > 0) next()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, step, warehouses.length, products.length])

  const finish = useCallback(() => {
    setActive(false)
    sessionStorage.removeItem('waysklad:onboarding-pending')
    localStorage.setItem(key, '1')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  const start = useCallback(() => {
    setStepIndex(0)
    setActive(true)
  }, [])

  const next = useCallback(() => {
    setStepIndex((i) => {
      const nextIndex = i + 1
      if (nextIndex >= STEPS.length) {
        finish()
        return i
      }
      return nextIndex
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finish])

  const skip = useCallback(() => {
    finish()
  }, [finish])

  const value = useMemo<OnboardingState>(
    () => ({ active, stepIndex, step, totalSteps: STEPS.length, start, next, skip }),
    [active, stepIndex, step, start, next, skip],
  )

  return <OnboardingContext.Provider value={value}>{children}</OnboardingContext.Provider>
}

export function useOnboarding(): OnboardingState {
  const ctx = useContext(OnboardingContext)
  if (!ctx) throw new Error('useOnboarding должен использоваться внутри OnboardingProvider')
  return ctx
}
