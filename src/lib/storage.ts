export interface StoredPayload<T> {
  version: number
  data: T
}

export type StorageFailure = 'corrupted' | 'quota' | 'unavailable'

export interface StorageResult<T> {
  data: T
  failure?: StorageFailure
}

export function parseJson<T>(raw: string | null): StorageResult<T | null> {
  if (raw === null) return { data: null }
  try {
    return { data: JSON.parse(raw) as T }
  } catch {
    return { data: null, failure: 'corrupted' }
  }
}

export function readJson<T>(key: string, fallback: T, validator?: (value: unknown) => value is T): StorageResult<T> {
  const parsed = parseJson<unknown>(localStorage.getItem(key))
  if (parsed.failure) return { data: fallback, failure: parsed.failure }
  if (parsed.data === null) return { data: fallback }
  if (validator && !validator(parsed.data)) return { data: fallback, failure: 'corrupted' }
  return { data: parsed.data as T }
}

export function readVersioned<T>(
  key: string,
  version: number,
  fallback: T,
  validator: (value: unknown) => value is T,
): StorageResult<T> {
  const parsed = parseJson<unknown>(localStorage.getItem(key))
  if (parsed.failure) return { data: fallback, failure: parsed.failure }
  if (parsed.data === null) return { data: fallback }
  if (!parsed.data || typeof parsed.data !== 'object') return { data: fallback, failure: 'corrupted' }
  const payload = parsed.data as Partial<StoredPayload<unknown>>
  if (payload.version !== version || !validator(payload.data)) return { data: fallback, failure: 'corrupted' }
  return { data: payload.data }
}

export function isQuotaError(error: unknown) {
  return error instanceof DOMException
    && (error.name === 'QuotaExceededError' || error.name === 'NS_ERROR_DOM_QUOTA_REACHED')
}

export function persistJson(key: string, value: unknown): StorageFailure | null {
  try {
    localStorage.setItem(key, JSON.stringify(value))
    return null
  } catch (error) {
    return isQuotaError(error) ? 'quota' : 'unavailable'
  }
}

export function persistVersioned<T>(key: string, version: number, data: T) {
  return persistJson(key, { version, data } satisfies StoredPayload<T>)
}
