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

type GuestStateBody = { favoriteIds: string[]; savedSearches: Array<Omit<RemoteSavedSearch, 'id' | 'createdAt'>> }
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

export async function importGuestState(body: GuestStateBody) {
  const signature = JSON.stringify(body)
  if (localStorage.getItem(IMPORTED_GUEST_STATE) === signature) return
  await api<void>('/account/import-guest-state', { method: 'POST', body: signature })
  localStorage.setItem(IMPORTED_GUEST_STATE, signature)
  clearPersistedGuestScope('112233:favorites:v2')
  clearPersistedGuestScope('112233:saved-searches:v3')
}
