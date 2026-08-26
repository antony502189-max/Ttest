import { api } from './client'

export type RemoteSavedSearch = {
  id: string
  name: string
  query: string
  rentalMode: 'long' | 'holiday'
  filters: Record<string, unknown>
  polygon: Array<{ lat: number; lng: number }>
  alertsEnabled: boolean
  createdAt: string
}

type GuestSavedSearch = Omit<RemoteSavedSearch, 'id' | 'createdAt'>
type GuestStateBody = { favoriteIds: string[]; savedSearches: GuestSavedSearch[] }
type ConsumedGuestState = { favoriteIds: string[]; savedSearchSignatures: string[] }
const IMPORTED_GUEST_STATE = '112233:imported-guest-state:v1'

export const getFavorites = () => api<string[]>('/favorites')
export const addFavorite = (listingId: string) => api<void>(`/favorites/${listingId}`, { method: 'PUT' })
export const removeFavorite = (listingId: string) => api<void>(`/favorites/${listingId}`, { method: 'DELETE' })
export const getDiscarded = () => api<string[]>('/discarded-listings')
export const clearDiscarded = () => api<void>('/discarded-listings', { method: 'DELETE' })
export const addDiscarded = (listingId: string) => api<void>(`/discarded-listings/${listingId}`, { method: 'PUT' })
export const removeDiscarded = (listingId: string) => api<void>(`/discarded-listings/${listingId}`, { method: 'DELETE' })
export const getSavedSearches = () => api<RemoteSavedSearch[]>('/saved-searches')
export const createSavedSearch = (body: Omit<RemoteSavedSearch, 'id' | 'createdAt'>) =>
  api<RemoteSavedSearch>('/saved-searches', { method: 'POST', body: JSON.stringify(body) })
export const updateSavedSearch = (id: string, body: Partial<Omit<RemoteSavedSearch, 'id' | 'createdAt' | 'rentalMode'>>) =>
  api<RemoteSavedSearch>(`/saved-searches/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const deleteSavedSearch = (id: string) => api<void>(`/saved-searches/${id}`, { method: 'DELETE' })

function clearPersistedGuestScope(key: string) {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return
    const parsed = JSON.parse(raw) as { version?: number; data?: Record<string, unknown> }
    if (!parsed.data || typeof parsed.data !== 'object') return
    const { guest: _guest, ...remaining } = parsed.data
    localStorage.setItem(key, JSON.stringify({ ...parsed, data: remaining }))
  } catch { /* Corrupted state is handled by the storage layer. */ }
}

function savedSearchSignature(search: GuestSavedSearch) {
  return JSON.stringify(search)
}

function readConsumedGuestState(): ConsumedGuestState {
  const empty: ConsumedGuestState = { favoriteIds: [], savedSearchSignatures: [] }
  try {
    const raw = localStorage.getItem(IMPORTED_GUEST_STATE)
    if (!raw) return empty
    const parsed = JSON.parse(raw) as Partial<ConsumedGuestState & GuestStateBody>
    if (Array.isArray(parsed.savedSearchSignatures)) {
      return {
        favoriteIds: Array.isArray(parsed.favoriteIds) ? parsed.favoriteIds.filter((id): id is string => typeof id === 'string') : [],
        savedSearchSignatures: parsed.savedSearchSignatures.filter((value): value is string => typeof value === 'string'),
      }
    }
    // Backward compatibility with the previous value, which stored the entire
    // imported GuestStateBody JSON as the marker.
    if (Array.isArray(parsed.favoriteIds) && Array.isArray(parsed.savedSearches)) {
      return {
        favoriteIds: parsed.favoriteIds.filter((id): id is string => typeof id === 'string'),
        savedSearchSignatures: parsed.savedSearches.map((search) => savedSearchSignature(search as GuestSavedSearch)),
      }
    }
  } catch { /* Treat an unreadable marker as no consumed state. */ }
  return empty
}

function writeConsumedGuestState(state: ConsumedGuestState) {
  try { localStorage.setItem(IMPORTED_GUEST_STATE, JSON.stringify(state)) } catch { /* Import still succeeded server-side. */ }
}

function resetConsumedGuestState() {
  try { localStorage.removeItem(IMPORTED_GUEST_STATE) } catch { /* Storage can be unavailable. */ }
}

export async function importGuestState(body: GuestStateBody) {
  // A reload after a successful migration rehydrates an empty guest scope. At
  // that point a future guest browsing session is new and may legitimately save
  // the same listing again, so release the prior consumed-state marker.
  if (!body.favoriteIds.length && !body.savedSearches.length) {
    resetConsumedGuestState()
    clearPersistedGuestScope('112233:favorites:v2')
    clearPersistedGuestScope('112233:saved-searches:v3')
    return
  }

  const consumed = readConsumedGuestState()
  const consumedFavorites = new Set(consumed.favoriteIds)
  const consumedSearches = new Set(consumed.savedSearchSignatures)
  const favoriteIds = body.favoriteIds.filter((id) => !consumedFavorites.has(id))
  const savedSearches = body.savedSearches.filter((search) => !consumedSearches.has(savedSearchSignature(search)))

  if (favoriteIds.length || savedSearches.length) {
    await api<void>('/account/import-guest-state', {
      method: 'POST',
      body: JSON.stringify({ favoriteIds, savedSearches }),
    })
    favoriteIds.forEach((id) => consumedFavorites.add(id))
    savedSearches.forEach((search) => consumedSearches.add(savedSearchSignature(search)))
    writeConsumedGuestState({
      favoriteIds: [...consumedFavorites],
      savedSearchSignatures: [...consumedSearches],
    })
  }

  // Persisted guest state is consumed after a successful import (or when every
  // item was already consumed). The in-memory React guest scope may live until
  // reload/logout transitions; the consumed sets above prevent it from leaking
  // into a second account on the same tab.
  clearPersistedGuestScope('112233:favorites:v2')
  clearPersistedGuestScope('112233:saved-searches:v3')
}
