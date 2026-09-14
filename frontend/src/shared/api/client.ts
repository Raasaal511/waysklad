const API_BASE = import.meta.env.VITE_API_URL ?? '/api'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function getToken(): string | null {
  return localStorage.getItem('access_token') ?? sessionStorage.getItem('access_token')
}

function handleSuspendedShop(status: number, message: string) {
  if (status !== 403) return
  const lower = message.toLowerCase()
  if (!lower.includes('заблок') && !lower.includes('suspended')) return
  // Не трогаем admin/customer токены — только сессию сотрудника магазина.
  localStorage.removeItem('access_token')
  localStorage.removeItem('user')
  sessionStorage.removeItem('access_token')
  sessionStorage.removeItem('user')
  if (!window.location.pathname.startsWith('/login')) {
    window.location.assign('/login?reason=suspended')
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const message = body?.detail ?? `Ошибка запроса: ${response.status}`
    const text = typeof message === 'string' ? message : JSON.stringify(message)
    handleSuspendedShop(response.status, text)
    throw new ApiError(response.status, text)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

async function requestWithTotal<T>(path: string, init?: RequestInit): Promise<{ data: T; total: number }> {
  const token = getToken()
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const message = body?.detail ?? `Ошибка запроса: ${response.status}`
    const text = typeof message === 'string' ? message : JSON.stringify(message)
    handleSuspendedShop(response.status, text)
    throw new ApiError(response.status, text)
  }

  const totalHeader = response.headers.get('X-Total-Count')
  const data = (await response.json()) as T
  return { data, total: totalHeader ? Number(totalHeader) : Array.isArray(data) ? data.length : 0 }
}

async function requestForm<T>(path: string, form: FormData, init?: RequestInit): Promise<T> {
  const token = getToken()
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    body: form,
    ...init,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const message = body?.detail ?? `Ошибка запроса: ${response.status}`
    const text = typeof message === 'string' ? message : JSON.stringify(message)
    handleSuspendedShop(response.status, text)
    throw new ApiError(response.status, text)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

async function requestBlob(path: string, init?: RequestInit): Promise<Blob> {
  const token = getToken()
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  })
  if (!response.ok) {
    throw new ApiError(response.status, `Ошибка запроса: ${response.status}`)
  }
  return response.blob()
}

export const api = {
  get: <T>(path: string, init?: RequestInit) => request<T>(path, init),
  getWithTotal: <T>(path: string, init?: RequestInit) => requestWithTotal<T>(path, init),
  getBlob: (path: string, init?: RequestInit) => requestBlob(path, init),
  post: <T>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined, ...init }),
  postForm: <T>(path: string, form: FormData, init?: RequestInit) => requestForm<T>(path, form, init),
  put: <T>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>(path, { method: 'PUT', body: body !== undefined ? JSON.stringify(body) : undefined, ...init }),
  patch: <T>(path: string, body?: unknown, init?: RequestInit) =>
    request<T>(path, { method: 'PATCH', body: body !== undefined ? JSON.stringify(body) : undefined, ...init }),
  delete: <T>(path: string, init?: RequestInit) => request<T>(path, { method: 'DELETE', ...init }),
}
