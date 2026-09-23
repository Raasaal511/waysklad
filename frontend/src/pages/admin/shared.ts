import { clearAdminToken, loadAdminToken, saveAdminToken } from '../../entities/admin/api'
import { ApiError } from '../../shared/api/client'
import { useState } from 'react'

export function useAdminAuth() {
  const [token, setToken] = useState(() => loadAdminToken())

  function login(accessToken: string) {
    saveAdminToken(accessToken)
    setToken(accessToken)
  }

  function logout() {
    clearAdminToken()
    setToken(null)
  }

  return { token, login, logout }
}

/** 401 — токен протух: разлогиниваем и объясняем, а не показываем «Ошибка запроса». */
export function handleAdminError(err: unknown, logout: () => void): string {
  if (err instanceof ApiError && err.status === 401) {
    logout()
    return 'Сессия истекла — войдите снова'
  }
  return err instanceof ApiError ? err.message : 'Ошибка запроса'
}
