import { createContext, useContext, useState, type ReactNode } from 'react'
import type { TokenResponse, User } from '../entities/auth/api'

interface AuthState {
  user: User | null
  login: (result: TokenResponse, remember?: boolean) => void
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

function readStoredUser(): User | null {
  const raw = localStorage.getItem('user') ?? sessionStorage.getItem('user')
  return raw ? (JSON.parse(raw) as User) : null
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(readStoredUser)

  function login(result: TokenResponse, remember = true) {
    const storage = remember ? localStorage : sessionStorage
    storage.setItem('access_token', result.access_token)
    storage.setItem('user', JSON.stringify(result.user))
    setUser(result.user)
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    sessionStorage.removeItem('access_token')
    sessionStorage.removeItem('user')
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth должен использоваться внутри AuthProvider')
  return ctx
}
