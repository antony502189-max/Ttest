const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(/\/$/, '')
let accessToken: string | null = null
let refreshPromise: Promise<boolean> | null = null

export class ApiError extends Error {
  status: number
  fieldErrors: Record<string, string>
  code?: string
  requestId?: string
  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}, code?: string, requestId?: string) { super(message); this.status = status; this.fieldErrors = fieldErrors; this.code = code; this.requestId = requestId }
}

type ValidationDetail = { loc?: Array<string | number>; msg?: string }

function validationFieldErrors(detail: ValidationDetail[] | undefined) {
  const fields: Record<string, string> = {}
  for (const error of detail ?? []) {
    const field = [...(error.loc ?? [])].reverse().find((part): part is string => typeof part === 'string' && !['body', 'query', 'path', 'header'].includes(part))
    if (field && !fields[field]) fields[field] = error.msg ?? 'Valor no válido.'
  }
  return fields
}

export function setAccessToken(token: string | null) { accessToken = token }
export function resolveApiUrl(path: string) {
  if (/^https?:\/\//.test(path)) return path
  const base = /^https?:\/\//.test(API_BASE_URL)
    ? API_BASE_URL
    : new URL(API_BASE_URL || '/', window.location.origin).toString().replace(/\/$/, '')
  return new URL(path, `${base}/`).toString()
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
    const requestHadAccessToken = Boolean(accessToken)
    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
    if (init.body && !headers.has('Content-Type') && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
    const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, credentials: 'include', signal: init.signal ?? controller.signal })
    // Refresh is recovery for an expired bearer token, not an authentication
    // mechanism for anonymous requests. Session hydration explicitly calls the
    // refresh endpoint on page load; requests made after logout must not revive
    // a cookie-only session merely because some endpoint returned 401.
    if (response.status === 401 && requestHadAccessToken && path !== '/auth/refresh' && !retried && await refresh()) return api<T>(path, init, true)
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as {
        detail?: string | ValidationDetail[] | { code?: string; message?: string; fieldErrors?: Record<string, string> }
        code?: string
        message?: string
        fieldErrors?: Record<string, string>
      }
      const detail = body.detail && !Array.isArray(body.detail) && typeof body.detail === 'object' ? body.detail : undefined
      const validationErrors = validationFieldErrors(Array.isArray(body.detail) ? body.detail : undefined)
      throw new ApiError(
        response.status,
        body.message ?? detail?.message ?? (Array.isArray(body.detail) ? 'Revisa los datos del formulario.' : typeof body.detail === 'string' ? body.detail : undefined) ?? 'No se pudo completar la solicitud.',
        body.fieldErrors ?? detail?.fieldErrors ?? validationErrors,
        body.code ?? detail?.code ?? (response.status === 422 ? 'VALIDATION_ERROR' : undefined),
        response.headers.get('X-Request-ID') ?? undefined,
      )
    }
    return response.status === 204 ? undefined as T : response.json() as Promise<T>
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(0, 'La solicitud tardó demasiado.', {}, init.signal ? 'REQUEST_ABORTED' : 'REQUEST_TIMEOUT')
    }
    if (error instanceof TypeError) {
      throw new ApiError(0, 'No se pudo conectar con el servidor.', {}, 'NETWORK_ERROR')
    }
    throw error
  } finally { window.clearTimeout(timeout) }
}
