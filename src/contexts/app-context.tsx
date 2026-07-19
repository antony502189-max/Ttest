import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import type { Filters, RentalMode } from '@/types'
import { defaultFilters } from '@/data/listings'

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

export function AppProvider({ children }: { children: ReactNode }) {
  const [rentalMode, setRentalMode] = useState<RentalMode>('long')
  const [query, setQuery] = useState('Tenerife')
  const [favorites, setFavorites] = useState<Set<string>>(readFavorites)
  const [filters, setFilters] = useState<Filters>(defaultFilters)

  const toggleFavorite = useCallback((id: string) => {
    setFavorites((current) => {
      const next = new Set(current)
      const wasSaved = next.has(id)
      if (wasSaved) next.delete(id)
      else next.add(id)
      localStorage.setItem('112233:favorites:v1', JSON.stringify([...next]))
      toast.success(wasSaved ? 'Eliminado de favoritos' : 'Guardado en favoritos')
      return next
    })
  }, [])

  const resetFilters = useCallback(() => setFilters(defaultFilters), [])
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

  const value = useMemo(() => ({ rentalMode, setRentalMode, query, setQuery, favorites, toggleFavorite, filters, setFilters, resetFilters, activeFilterCount }), [rentalMode, query, favorites, toggleFavorite, filters, resetFilters, activeFilterCount])
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) throw new Error('useApp debe usarse dentro de AppProvider')
  return context
}
