import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import type { Filters, RentalMode } from '@/types'
import { defaultFilters } from '@/data/listings'

export interface SavedSearch {
  id: string
  query: string
  rentalMode: RentalMode
  filters: Filters
  alerts: boolean
  createdAt: string
}

interface AppState {
  rentalMode: RentalMode
  setRentalMode: (mode: RentalMode) => void
  query: string
  setQuery: (query: string) => void
  favorites: Set<string>
  toggleFavorite: (id: string) => void
  filters: Filters
  setFilters: (filters: Filters) => void
  resetFilters: () => void
  activeFilterCount: number
  searchHistory: string[]
  addSearchHistory: (query: string) => void
  clearSearchHistory: () => void
  savedSearches: SavedSearch[]
  saveCurrentSearch: () => void
  removeSavedSearch: (id: string) => void
  toggleSearchAlerts: (id: string) => void
}

const AppContext = createContext<AppState | null>(null)

const readFavorites = () => {
  try {
    const raw = localStorage.getItem('112233:favorites:v1')
    return new Set<string>(raw ? JSON.parse(raw) : [])
  } catch {
    return new Set<string>()
  }
}

const readJson = <T,>(key: string, fallback: T): T => {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) as T : fallback
  } catch {
    return fallback
  }
}

const persist = (key: string, value: unknown) => {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* Storage may be unavailable. */ }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [rentalMode, setRentalMode] = useState<RentalMode>('long')
  const [query, setQuery] = useState('Tenerife')
  const [favorites, setFavorites] = useState<Set<string>>(readFavorites)
  const [filters, setFilters] = useState<Filters>(defaultFilters)
  const [searchHistory, setSearchHistory] = useState<string[]>(() => readJson('112233:search-history:v1', []))
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>(() => readJson('112233:saved-searches:v1', []))

  useEffect(() => persist('112233:favorites:v1', [...favorites]), [favorites])
  useEffect(() => persist('112233:search-history:v1', searchHistory), [searchHistory])
  useEffect(() => persist('112233:saved-searches:v1', savedSearches), [savedSearches])

  const toggleFavorite = useCallback((id: string) => {
    const next = new Set(favorites)
    const wasSaved = next.has(id)
    if (wasSaved) next.delete(id)
    else next.add(id)
    setFavorites(next)
    toast.success(wasSaved ? 'Eliminado de favoritos' : 'Guardado en favoritos')
  }, [favorites])

  const resetFilters = useCallback(() => setFilters(defaultFilters), [])
  const addSearchHistory = useCallback((nextQuery: string) => {
    const normalized = nextQuery.trim()
    if (!normalized) return
    setSearchHistory([normalized, ...searchHistory.filter((item) => item.toLocaleLowerCase() !== normalized.toLocaleLowerCase())].slice(0, 5))
  }, [searchHistory])
  const clearSearchHistory = useCallback(() => {
    setSearchHistory([])
    persist('112233:search-history:v1', [])
  }, [])
  const saveCurrentSearch = useCallback(() => {
    const duplicate = savedSearches.some((item) => item.query === query && item.rentalMode === rentalMode && JSON.stringify(item.filters) === JSON.stringify(filters))
    if (duplicate) {
      toast.info('Esta búsqueda ya está guardada')
      return
    }
    setSavedSearches([{ id: `search-${Date.now()}`, query, rentalMode, filters, alerts: true, createdAt: new Date().toISOString() }, ...savedSearches])
    toast.success('Búsqueda guardada. Te avisaremos de nuevos anuncios.')
  }, [filters, query, rentalMode, savedSearches])
  const removeSavedSearch = useCallback((id: string) => {
    setSavedSearches(savedSearches.filter((item) => item.id !== id))
    toast.success('Búsqueda eliminada')
  }, [savedSearches])
  const toggleSearchAlerts = useCallback((id: string) => {
    setSavedSearches(savedSearches.map((item) => item.id === id ? { ...item, alerts: !item.alerts } : item))
  }, [savedSearches])
  const activeFilterCount = useMemo(() => {
    let count = 0
    if (filters.minPrice !== 0 || filters.maxPrice !== 1000) count++
    if (filters.areas.length) count++
    if (filters.roomType !== 'Cualquiera') count++
    if (filters.available) count++
    if (filters.minStay !== 'Cualquiera') count++
    if (filters.conditions.length) count++
    if (filters.bathroom !== 'Cualquiera') count++
    if (filters.kitchen !== 'Cualquiera') count++
    if (filters.furnished) count++
    if (filters.billsIncluded) count++
    if (filters.deposit !== 'Cualquiera') count++
    if (filters.occupants !== 'Cualquiera') count++
    return count
  }, [filters])

  const value = useMemo(() => ({ rentalMode, setRentalMode, query, setQuery, favorites, toggleFavorite, filters, setFilters, resetFilters, activeFilterCount, searchHistory, addSearchHistory, clearSearchHistory, savedSearches, saveCurrentSearch, removeSavedSearch, toggleSearchAlerts }), [rentalMode, query, favorites, toggleFavorite, filters, resetFilters, activeFilterCount, searchHistory, addSearchHistory, clearSearchHistory, savedSearches, saveCurrentSearch, removeSavedSearch, toggleSearchAlerts])
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) throw new Error('useApp debe usarse dentro de AppProvider')
  return context
}
