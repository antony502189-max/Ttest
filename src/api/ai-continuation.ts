// Locators only. No prompt, criteria, cards, token or pending payload is stored.
export type AIOperationLocator = { key: string; expectedVersion: number; createdAt: number }
export type AIContinuation = { sessionId: string; resultRef?: string; operation?: AIOperationLocator }
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
export const continuationKey = (identity: string) => `112233:ai-continuation:v1:${identity}`
export function readAIContinuation(identity: string): AIContinuation | null {
  try {
    const raw = sessionStorage.getItem(continuationKey(identity))
    if (!raw || raw.length > 512) return null
    const value = JSON.parse(raw)
    if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).some(key => !['sessionId', 'resultRef', 'operation'].includes(key)) ||
      typeof value.sessionId !== 'string' || !uuid.test(value.sessionId) ||
      (value.resultRef !== undefined && (typeof value.resultRef !== 'string' || !uuid.test(value.resultRef)))) return null
    if (value.operation !== undefined) {
      const op = value.operation
      if (!op || typeof op !== 'object' || Array.isArray(op) ||
        Object.keys(op).sort().join(',') !== 'createdAt,expectedVersion,key' ||
        typeof op.key !== 'string' || !uuid.test(op.key) ||
        !Number.isSafeInteger(op.expectedVersion) || op.expectedVersion < 0 || op.expectedVersion > 2147483647 ||
        !Number.isSafeInteger(op.createdAt) || op.createdAt > Date.now() || Date.now() - op.createdAt > 86400000) return null
    }
    return value
  } catch { return null }
}
export function storeAIContinuation(identity: string, value: AIContinuation | null) {
  try {
    if (value) sessionStorage.setItem(continuationKey(identity), JSON.stringify(value))
    else sessionStorage.removeItem(continuationKey(identity))
  } catch { /* Storage is optional; the server remains authoritative. */ }
}
