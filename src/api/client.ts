const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1').replace(/\/$/, '')
let accessToken: string | null = null
let refreshPromise: Promise<boolean> | null = null

export class ApiError extends Error {
  status: number
  fieldErrors: Record<string, string>
  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) { super(message); this.status = status; this.fieldErrors = fieldErrors }
}

export function setAccessToken(token: string | null) { accessToken = token }
export function resolveApiUrl(path: string) {
  return /^https?:\/\//.test(path) ? path : new URL(path, `${API_BASE_URL}/`).toString()
}

async function performRefresh() {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 15_000)
  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST', credentials: 'include', signal: controller.signal,
    })
    if (!response.ok) {
      accessToken = null
      return false
    }
    const body = await response.json() as { accessToken: string }
    accessToken = body.accessToken
    return true
  } catch {
    accessToken = null
    return false
  } finally {
    window.clearTimeout(timeout)
  }
}

function refresh() {
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => { refreshPromise = null })
  }
  return refreshPromise
}

export async function api<T>(path: string, init: RequestInit = {}, retried = false): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 15_000)
  try {
    const headers = new Headers(init.headers)
    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
    if (init.body && !headers.has('Content-Type') && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
    const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, credentials: 'include', signal: controller.signal })
    if (response.status === 401 && path !== '/auth/refresh' && !retried && await refresh()) return api<T>(path, init, true)
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { detail?: string; message?: string; fieldErrors?: Record<string, string> }
      throw new ApiError(response.status, body.message ?? body.detail ?? 'No se pudo completar la solicitud.', body.fieldErrors)
    }
    return response.status === 204 ? undefined as T : response.json() as Promise<T>
  } finally { window.clearTimeout(timeout) }
}
