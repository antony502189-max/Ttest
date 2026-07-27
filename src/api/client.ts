const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1').replace(/\/$/, '')
let accessToken: string | null = null
export class ApiError extends Error {
  status: number
  fieldErrors: Record<string, string>
  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) { super(message); this.status = status; this.fieldErrors = fieldErrors }
}
export function setAccessToken(token: string | null) { accessToken = token }
async function refresh() {
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, { method: 'POST', credentials: 'include' })
  if (!response.ok) return false
  const body = await response.json() as { accessToken: string }
  accessToken = body.accessToken
  return true
}
export async function api<T>(path: string, init: RequestInit = {}, retried = false): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 15_000)
  try {
    const headers = new Headers(init.headers)
    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
    if (init.body && !headers.has('Content-Type') && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
    const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, credentials: 'include', signal: controller.signal })
    if (response.status === 401 && !retried && await refresh()) return api<T>(path, init, true)
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { detail?: string; message?: string; fieldErrors?: Record<string, string> }
      throw new ApiError(response.status, body.message ?? body.detail ?? 'No se pudo completar la solicitud.', body.fieldErrors)
    }
    return response.status === 204 ? undefined as T : response.json() as Promise<T>
  } finally { window.clearTimeout(timeout) }
}
