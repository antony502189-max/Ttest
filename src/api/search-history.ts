import { api } from './client'

export const getSearchHistory = () => api<string[]>('/search-history')
export const addSearchHistory = (query: string) => api<void>('/search-history', { method: 'POST', body: JSON.stringify({ query }) })
export const clearSearchHistory = () => api<void>('/search-history', { method: 'DELETE' })
