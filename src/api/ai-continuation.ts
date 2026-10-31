// Locators only. No prompt, criteria, cards, token or pending payload is stored.
export type AIContinuation = { sessionId: string; resultRef?: string }
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
export const continuationKey = (identity: string) => `112233:ai-continuation:v1:${identity}`
export function readAIContinuation(identity: string): AIContinuation | null {
  try {
    const raw = sessionStorage.getItem(continuationKey(identity))
    if (!raw || raw.length > 256) return null
    const value = JSON.parse(raw)
    if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).some(key => !['sessionId', 'resultRef'].includes(key)) ||
      typeof value.sessionId !== 'string' || !uuid.test(value.sessionId) ||
      (value.resultRef !== undefined && (typeof value.resultRef !== 'string' || !uuid.test(value.resultRef)))) return null
    return value
  } catch { return null }
}
export function storeAIContinuation(identity: string, value: AIContinuation | null) {
  try {
    if (value) sessionStorage.setItem(continuationKey(identity), JSON.stringify(value))
    else sessionStorage.removeItem(continuationKey(identity))
  } catch { /* Storage is optional; the server remains authoritative. */ }
}
