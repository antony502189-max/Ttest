import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { defaultFilters, initialListings } from '@/data/listings'
import { getActiveFilterKeys } from '@/lib/search'
import type { DemoUser, Filters, Listing, ListingStatus, MapPolygonPoint, RentalMode, ReportRecord, UserRole } from '@/types'

export interface SavedSearch {
  id: string
  query: string
  rentalMode: RentalMode
  filters: Filters
  alerts: boolean
  createdAt: string
  polygon: MapPolygonPoint[]
}

type RegisterInput = { name: string; email: string; password: string; role: UserRole }
type ProfileUpdate = Partial<Omit<DemoUser, 'id' | 'email' | 'password' | 'role'>>

interface AppState {
  rentalMode: RentalMode
  setRentalMode: (mode: RentalMode) => void
  query: string
  setQuery: (query: string) => void
  favorites: Set<string>
  toggleFavorite: (id: string) => void
  discarded: Set<string>
  discardListing: (id: string) => void
  restoreDiscarded: () => void
  filters: Filters
  setFilters: (filters: Filters) => void
  resetFilters: () => void
  activeFilterCount: number
  searchHistory: string[]
  addSearchHistory: (query: string) => void
  clearSearchHistory: () => void
  savedSearches: SavedSearch[]
  saveCurrentSearch: () => void
  restoreSavedSearch: (id: string) => SavedSearch | undefined
  removeSavedSearch: (id: string) => void
  toggleSearchAlerts: (id: string) => void
  mapPolygon: MapPolygonPoint[]
  setMapPolygon: (points: MapPolygonPoint[]) => void
  clearMapPolygon: () => void
  allListings: Listing[]
  createListing: (listing: Listing) => void
  updateListing: (id: string, listing: Listing) => void
  deleteListing: (id: string) => void
  setListingStatus: (id: string, status: ListingStatus) => void
  renewListing: (id: string) => void
  reports: ReportRecord[]
  addReport: (listingId: string, reason: string, comment: string) => void
  users: DemoUser[]
  currentUser: DemoUser | null
  login: (email: string, password: string) => string | null
  register: (input: RegisterInput) => string | null
  logout: () => void
  updateProfile: (changes: ProfileUpdate) => void
  deleteAccount: () => void
  toggleUserBlocked: (id: string) => void
}

const AppContext = createContext<AppState | null>(null)

const demoUsers: DemoUser[] = [
  { id: 'tenant-demo', name: 'Lucía Demo', email: 'inquilina@112233.es', password: 'demo112233', role: 'tenant', phone: '+34 600 000 112', whatsapp: '+34 600 000 112', telegram: '@lucia_demo', about: 'Busco una habitación tranquila en Tenerife.', initials: 'LD', showPhone: true, allowMessaging: true },
  { id: 'host-demo', name: 'Carlos Anfitrión', email: 'anfitrion@112233.es', password: 'demo112233', role: 'host', phone: '+34 600 112 233', whatsapp: '+34 600 112 233', telegram: '@carlos_demo', about: 'Publico habitaciones con condiciones claras.', initials: 'CA', showPhone: true, allowMessaging: true },
  { id: 'admin-demo', name: 'Ana Moderación', email: 'admin@112233.es', password: 'admin112233', role: 'admin', phone: '+34 600 332 211', whatsapp: '+34 600 332 211', telegram: '@ana_admin_demo', about: 'Cuenta de administración para esta demo local.', initials: 'AM', showPhone: false, allowMessaging: false },
]

const readJson = <T,>(key: string, fallback: T): T => {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) as T : fallback
  } catch {
    return fallback
  }
}

const persist = (key: string, value: unknown) => {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* Private mode or quota errors keep the session usable. */ }
}

const validListings = (value: unknown): value is Listing[] => Array.isArray(value) && value.length >= 30 && value.every((item) => item && typeof item.id === 'string' && Array.isArray(item.images) && typeof item.publishedAt === 'string')
const readListings = () => {
  const stored = readJson<unknown>('112233:listings:v2', null)
  return validListings(stored) ? stored : initialListings
}

const readSavedSearches = () => readJson<SavedSearch[]>('112233:saved-searches:v2', []).map((item) => ({ ...item, filters: { ...defaultFilters, ...item.filters }, polygon: item.polygon ?? [] }))

export function AppProvider({ children }: { children: ReactNode }) {
  const [rentalMode, setRentalMode] = useState<RentalMode>('long')
  const [query, setQuery] = useState('Tenerife')
  const [favorites, setFavorites] = useState<Set<string>>(() => new Set(readJson<string[]>('112233:favorites:v1', [])))
  const [discarded, setDiscarded] = useState<Set<string>>(() => new Set(readJson<string[]>('112233:discarded:v1', [])))
  const [filters, setFilters] = useState<Filters>({ ...defaultFilters })
  const [searchHistory, setSearchHistory] = useState<string[]>(() => readJson('112233:search-history:v1', []))
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>(readSavedSearches)
  const [mapPolygon, setMapPolygonState] = useState<MapPolygonPoint[]>(() => readJson('112233:map-polygon:v1', []))
  const [allListings, setAllListings] = useState<Listing[]>(readListings)
  const [reports, setReports] = useState<ReportRecord[]>(() => readJson('112233:reports:v1', []))
  const [users, setUsers] = useState<DemoUser[]>(() => readJson('112233:users:v1', demoUsers))
  const [currentUserId, setCurrentUserId] = useState<string | null>(() => readJson('112233:session:v1', null))

  useEffect(() => persist('112233:favorites:v1', [...favorites]), [favorites])
  useEffect(() => persist('112233:discarded:v1', [...discarded]), [discarded])
  useEffect(() => persist('112233:search-history:v1', searchHistory), [searchHistory])
  useEffect(() => persist('112233:saved-searches:v2', savedSearches), [savedSearches])
  useEffect(() => persist('112233:map-polygon:v1', mapPolygon), [mapPolygon])
  useEffect(() => persist('112233:listings:v2', allListings), [allListings])
  useEffect(() => persist('112233:reports:v1', reports), [reports])
  useEffect(() => persist('112233:users:v1', users), [users])
  useEffect(() => persist('112233:session:v1', currentUserId), [currentUserId])

  const currentUser = users.find((user) => user.id === currentUserId) ?? null
  const toggleFavorite = useCallback((id: string) => setFavorites((current) => {
    const next = new Set(current)
    const wasSaved = next.has(id)
    if (wasSaved) next.delete(id); else next.add(id)
    toast.success(wasSaved ? 'Eliminado de favoritos' : 'Guardado en favoritos')
    return next
  }), [])
  const discardListing = useCallback((id: string) => setDiscarded((current) => new Set(current).add(id)), [])
  const restoreDiscarded = useCallback(() => setDiscarded(new Set()), [])
  const resetFilters = useCallback(() => setFilters({ ...defaultFilters }), [])
  const addSearchHistory = useCallback((nextQuery: string) => setSearchHistory((current) => {
    const normalized = nextQuery.trim()
    if (!normalized) return current
    return [normalized, ...current.filter((item) => item.toLocaleLowerCase() !== normalized.toLocaleLowerCase())].slice(0, 8)
  }), [])
  const clearSearchHistory = useCallback(() => setSearchHistory([]), [])
  const saveCurrentSearch = useCallback(() => setSavedSearches((current) => {
    const duplicate = current.some((item) => item.query === query && item.rentalMode === rentalMode && JSON.stringify(item.filters) === JSON.stringify(filters) && JSON.stringify(item.polygon) === JSON.stringify(mapPolygon))
    if (duplicate) { toast.info('Esta búsqueda ya está guardada'); return current }
    toast.success('Búsqueda guardada. Te avisaremos de nuevos anuncios.')
    return [{ id: `search-${Date.now()}`, query, rentalMode, filters: { ...filters }, alerts: true, createdAt: new Date().toISOString(), polygon: mapPolygon }, ...current]
  }), [filters, mapPolygon, query, rentalMode])
  const restoreSavedSearch = useCallback((id: string) => {
    const found = savedSearches.find((item) => item.id === id)
    if (found) { setQuery(found.query); setRentalMode(found.rentalMode); setFilters(found.filters); setMapPolygonState(found.polygon) }
    return found
  }, [savedSearches])
  const removeSavedSearch = useCallback((id: string) => setSavedSearches((current) => current.filter((item) => item.id !== id)), [])
  const toggleSearchAlerts = useCallback((id: string) => setSavedSearches((current) => current.map((item) => item.id === id ? { ...item, alerts: !item.alerts } : item)), [])
  const setMapPolygon = useCallback((points: MapPolygonPoint[]) => setMapPolygonState(points), [])
  const clearMapPolygon = useCallback(() => setMapPolygonState([]), [])

  const createListing = useCallback((listing: Listing) => { setAllListings((current) => [listing, ...current]); toast.success('Anuncio publicado y guardado en Mis anuncios') }, [])
  const updateListing = useCallback((id: string, listing: Listing) => setAllListings((current) => current.map((item) => item.id === id ? listing : item)), [])
  const deleteListing = useCallback((id: string) => setAllListings((current) => current.filter((item) => item.id !== id)), [])
  const setListingStatus = useCallback((id: string, status: ListingStatus) => setAllListings((current) => current.map((item) => item.id === id ? { ...item, status } : item)), [])
  const renewListing = useCallback((id: string) => setAllListings((current) => current.map((item) => item.id === id ? { ...item, expiresAt: new Date(Date.now() + 30 * 86_400_000).toISOString().slice(0, 10) } : item)), [])
  const addReport = useCallback((listingId: string, reason: string, comment: string) => setReports((current) => [{ id: `REP-${Date.now().toString().slice(-6)}`, listingId, reason, comment, createdAt: new Date().toISOString(), status: 'Abierta' }, ...current]), [])

  const login = useCallback((email: string, password: string) => {
    const user = users.find((item) => item.email.toLocaleLowerCase() === email.trim().toLocaleLowerCase())
    if (!user || user.password !== password) return 'Email o contraseña incorrectos. Usa una cuenta demo o regístrate.'
    if (user.blocked) return 'Esta cuenta está bloqueada en la demo.'
    setCurrentUserId(user.id)
    return null
  }, [users])
  const register = useCallback((input: RegisterInput) => {
    if (users.some((user) => user.email.toLocaleLowerCase() === input.email.toLocaleLowerCase())) return 'Ya existe una cuenta con este email.'
    const initials = input.name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toLocaleUpperCase()
    const user: DemoUser = { id: `user-${Date.now()}`, ...input, phone: '', whatsapp: '', telegram: '', about: '', initials, showPhone: false, allowMessaging: true }
    setUsers((current) => [...current, user])
    setCurrentUserId(user.id)
    return null
  }, [users])
  const logout = useCallback(() => setCurrentUserId(null), [])
  const updateProfile = useCallback((changes: ProfileUpdate) => {
    if (!currentUserId) return
    setUsers((current) => current.map((user) => user.id === currentUserId ? { ...user, ...changes } : user))
    toast.success('Perfil actualizado')
  }, [currentUserId])
  const deleteAccount = useCallback(() => {
    if (!currentUserId) return
    setUsers((current) => current.filter((user) => user.id !== currentUserId))
    setCurrentUserId(null)
  }, [currentUserId])
  const toggleUserBlocked = useCallback((id: string) => setUsers((current) => current.map((user) => user.id === id ? { ...user, blocked: !user.blocked } : user)), [])

  const activeFilterCount = useMemo(() => getActiveFilterKeys(filters).length, [filters])
  const value = useMemo<AppState>(() => ({ rentalMode, setRentalMode, query, setQuery, favorites, toggleFavorite, discarded, discardListing, restoreDiscarded, filters, setFilters, resetFilters, activeFilterCount, searchHistory, addSearchHistory, clearSearchHistory, savedSearches, saveCurrentSearch, restoreSavedSearch, removeSavedSearch, toggleSearchAlerts, mapPolygon, setMapPolygon, clearMapPolygon, allListings, createListing, updateListing, deleteListing, setListingStatus, renewListing, reports, addReport, users, currentUser, login, register, logout, updateProfile, deleteAccount, toggleUserBlocked }), [rentalMode, query, favorites, toggleFavorite, discarded, discardListing, restoreDiscarded, filters, resetFilters, activeFilterCount, searchHistory, addSearchHistory, clearSearchHistory, savedSearches, saveCurrentSearch, restoreSavedSearch, removeSavedSearch, toggleSearchAlerts, mapPolygon, setMapPolygon, clearMapPolygon, allListings, createListing, updateListing, deleteListing, setListingStatus, renewListing, reports, addReport, users, currentUser, login, register, logout, updateProfile, deleteAccount, toggleUserBlocked])
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) throw new Error('useApp debe usarse dentro de AppProvider')
  return context
}
