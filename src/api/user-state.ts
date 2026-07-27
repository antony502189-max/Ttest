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
export const importGuestState = (body: { favoriteIds: string[]; savedSearches: Array<Omit<RemoteSavedSearch, 'id' | 'createdAt'>> }) =>
  api<void>('/account/import-guest-state', { method: 'POST', body: JSON.stringify(body) })
