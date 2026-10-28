import { api } from '@/api/client'
import { toCardListing, type ListingCardDto, type ListingCardPage, type ListingMapMarker } from '@/api/listings'
import type { AICommittedIntent, AIIntent } from '@/api/ai-intent'
import type { RentalMode } from '@/types'

export type AICapabilities = { text: boolean; map: boolean; voice: boolean; saved_searches: boolean }
export type AISession = { intent: AIIntent; expires_at: string }
export type AIMessage = { idempotency_key: string; session_id: string; expected_version: number; text: string }
export type AIBudgetPrice = { listing_id: string; matched_amount: number; matched_period: 'monthly' | 'weekly' | 'nightly'; display_amount: number | null; display_period: 'monthly' | 'nightly'; currency: 'EUR'; confirmation: 'current_source_proof' }
type CardResponse = { budget_prices?: AIBudgetPrice[]; cards: { items: ListingCardDto[]; total: number; nextCursor: string | null; previousCursor: string | null }; intent_hash: string }
export type AIExecution = {
  operation: { status: 'reserved' | 'running' | 'succeeded' | 'failed'; failure_code: string | null; remaining: number; receipt: { result_ref: string; count: number } | null }
  cards_error?: string | null
  cards: CardResponse | null
}

const headers = { 'X-AI-Request': '1' }
export const aiCapabilities = (signal: AbortSignal) => api<AICapabilities>('/ai-search/capabilities', { signal, cache: 'no-store' })
export async function createAISession(key: string, signal: AbortSignal, rentalMode?: RentalMode) {
  // Establish ownership before any session transaction can commit. Lost
  // bootstrap responses cannot strand a session behind a missing cookie.
  await api('/ai-search/identity', { method: 'POST', headers, signal, cache: 'no-store' })
  return api<AISession>('/ai-search/sessions', { method: 'POST', headers,
    body: JSON.stringify({ idempotency_key: key, ...(rentalMode ? { rental_mode: rentalMode } : {}) }), signal, cache: 'no-store' })
}
export const resetAISession = (session: AISession, key: string, signal: AbortSignal, rentalMode?: RentalMode) => api<AISession>(`/ai-search/sessions/${encodeURIComponent(session.intent.session_id)}/reset`, {
  method: 'POST', headers, body: JSON.stringify({ expected_version: session.intent.version, idempotency_key: key, ...(rentalMode ? { rental_mode: rentalMode } : {}) }), signal, cache: 'no-store',
})
export const getAISession = (id: string, signal: AbortSignal) => api<AISession>(`/ai-search/sessions/${encodeURIComponent(id)}`, { signal, cache: 'no-store' })
export const getAIResult = (ref: string, signal: AbortSignal) => api<AICommittedIntent>(`/ai-search/results/${encodeURIComponent(ref)}`, { signal, cache: 'no-store' })
export const getAIQuota = (signal: AbortSignal) => api<{ remaining: number }>('/ai-search/quota', { signal, cache: 'no-store' })
export const sendAIMessage = (message: AIMessage, signal: AbortSignal) => api<AIExecution>('/ai-search/query', {
  method: 'POST', headers, body: JSON.stringify({ ...message, search: { limit: 6 } }), signal, cache: 'no-store',
})
export async function aiResultPage(ref: string, cursor: string | undefined, signal: AbortSignal) {
  return api<CardResponse>(`/ai-search/results/${encodeURIComponent(ref)}/cards`, {
    method: 'POST', headers, body: JSON.stringify({ search: { limit: 6, cursor } }), signal, cache: 'no-store',
  })
}
export const aiResultMap = (ref: string, viewport: { north: number; south: number; east: number; west: number; zoom: number }, signal: AbortSignal) =>
  api<{ map: { items: ListingMapMarker[] }; intent_hash: string }>(`/ai-search/results/${encodeURIComponent(ref)}/map`, {
    method: 'POST', headers, body: JSON.stringify({ search: viewport }), signal, cache: 'no-store',
  })
export function aiCardPage(response: CardResponse): ListingCardPage {
  const seen = new Set<string>()
  return { ...response.cards, items: response.cards.items.filter(item => {
    if (seen.has(item.id)) return false
    seen.add(item.id)
    return true
  }).map(toCardListing) }
}
