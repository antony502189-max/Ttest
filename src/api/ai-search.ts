import { api } from '@/api/client'
import { toCardListing, type ListingCardDto, type ListingCardPage } from '@/api/listings'

export type AICapabilities = { text: boolean; map: boolean; voice: boolean; saved_searches: boolean }
export type AISession = { intent: { session_id: string; version: number }; expires_at: string }
export type AIMessage = { idempotency_key: string; session_id: string; expected_version: number; text: string }
export type AIBudgetPrice = { listing_id: string; matched_amount: number; matched_period: 'monthly' | 'weekly' | 'nightly'; display_amount: number | null; display_period: 'monthly' | 'nightly'; currency: 'EUR'; confirmation: 'current_source_proof' }
type CardResponse = { budget_prices?: AIBudgetPrice[]; cards: { items: ListingCardDto[]; total: number; nextCursor: string | null; previousCursor: string | null }; intent_hash: string }
export type AIExecution = {
  operation: { status: 'reserved' | 'running' | 'succeeded' | 'failed'; failure_code: string | null; remaining: number; receipt: { result_ref: string; count: number } | null }
  cards: CardResponse | null
}

const headers = { 'X-AI-Request': '1' }
export const aiCapabilities = (signal: AbortSignal) => api<AICapabilities>('/ai-search/capabilities', { signal, cache: 'no-store' })
export const createAISession = (signal: AbortSignal) => api<AISession>('/ai-search/sessions', { method: 'POST', headers, signal, cache: 'no-store' })
export const getAISession = (id: string, signal: AbortSignal) => api<AISession>(`/ai-search/sessions/${encodeURIComponent(id)}`, { signal, cache: 'no-store' })
export const getAIQuota = (signal: AbortSignal) => api<{ remaining: number }>('/ai-search/quota', { signal, cache: 'no-store' })
export const sendAIMessage = (message: AIMessage, signal: AbortSignal) => api<AIExecution>('/ai-search/query', {
  method: 'POST', headers, body: JSON.stringify({ ...message, search: { limit: 6 } }), signal, cache: 'no-store',
})
export async function aiResultPage(ref: string, cursor: string, signal: AbortSignal) {
  return api<CardResponse>(`/ai-search/results/${encodeURIComponent(ref)}/cards`, {
    method: 'POST', headers, body: JSON.stringify({ search: { limit: 6, cursor } }), signal, cache: 'no-store',
  })
}
export function aiCardPage(response: CardResponse): ListingCardPage {
  const seen = new Set<string>()
  return { ...response.cards, items: response.cards.items.filter(item => {
    if (seen.has(item.id)) return false
    seen.add(item.id)
    return true
  }).map(toCardListing) }
}
