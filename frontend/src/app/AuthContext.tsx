import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import type { TokenResponse, User } from '../entities/auth/api'
import { clearReceiveDraft } from '../pages/stock/receiveDraft'
import { clearAllRestockCarts } from '../pages/stock/restockCart'
import { scopedKey } from '../shared/lib/scopedStorage'
import { disablePush } from '../entities/notification/push'

// Черновик "Новой продажи" (SalePage.tsx) хранит полные объекты товаров
// (название, цену) в localStorage — держим ключ строкой здесь, а не
// импортируем SalePage.tsx целиком (там огромный файл со своими тяжёлыми
// зависимостями) ради одной константы.
function saleDraftKey(): string {
  return scopedKey('sale-draft')
}

interface AuthState {
  user: User | null
  login: (result: TokenResponse, remember?: boolean) => void
  /** Поля своего профиля изменились без нового токена (например, привязали Telegram). */
  patchUser: (patch: Partial<User>) => void
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

function readStoredUser(): User | null {
  const raw = localStorage.getItem('user') ?? sessionStorage.getItem('user')
  return raw ? (JSON.parse(raw) as User) : null
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(readStoredUser)

  // Разовая уборка мусора от версии кода до scopedKey() — голые
  // 'waysklad:sale-draft'/'waysklad:receive-draft' без префикса пользователя
  // никем больше не читаются, но и сами не удаляются: без этого остаются в
  // localStorage навсегда и путают при отладке (выглядят как "потерянные"
  // данные). Только голый ключ — НЕ clearAllScoped: та чистит scoped-ключи
  // всех пользователей и стёрла бы черновик текущего залогиненного при
  // каждой загрузке страницы.
  useEffect(() => {
    localStorage.removeItem('waysklad:sale-draft')
    localStorage.removeItem('waysklad:receive-draft')
  }, [])

  function login(result: TokenResponse, remember?: boolean) {
    // при смене пароля вызывающий не знает, в каком storage лежит текущая
    // сессия — по умолчанию сохраняем туда же, где токен уже лежит
    const wasRemembered = remember ?? localStorage.getItem('access_token') !== null
    const storage = wasRemembered ? localStorage : sessionStorage
    storage.setItem('access_token', result.access_token)
    storage.setItem('user', JSON.stringify(result.user))
    setUser(result.user)
  }

  function patchUser(patch: Partial<User>) {
    setUser((prev) => {
      if (!prev) return prev
      const next = { ...prev, ...patch }
      // туда же, где лежит сессия, — иначе после перезагрузки снова старое значение
      const storage = localStorage.getItem('user') !== null ? localStorage : sessionStorage
      storage.setItem('user', JSON.stringify(next))
      return next
    })
  }

  function logout() {
    // Уведомления на телефон уходят тому, кто их включил: после выхода этому
    // браузеру больше ничего не шлём. Токен — сейчас, ниже он стирается.
    void disablePush(
      localStorage.getItem('access_token') ?? sessionStorage.getItem('access_token') ?? undefined,
    )

    // scopedKey() читает 'user' из storage — чистим scoped-данные ДО того,
    // как его сотрём, иначе не найдём ключи именно этого (выходящего) пользователя.
    // Реальная защита от утечки между аккаунтами — сам scopedKey (данные разных
    // user.id физически не пересекаются с момента сохранения); это лишь уборка.
    localStorage.removeItem(saleDraftKey())
    clearReceiveDraft()
    clearAllRestockCarts()

    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    sessionStorage.removeItem('access_token')
    sessionStorage.removeItem('user')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, patchUser, logout }}>{children}</AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth должен использоваться внутри AuthProvider')
  return ctx
}
