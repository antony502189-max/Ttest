import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { defaultFilters, initialListings } from '@/data/listings'
import { expireListing, isListingLike, normalizeListing } from '@/lib/listings'
import { getActiveFilterKeys } from '@/lib/search'
import { parseJson, persistJson, persistVersioned, readJson, readVersioned, type StorageFailure } from '@/lib/storage'
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
type UserScopedState<T> = Record<string, T>

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
  closeListing: (id: string) => void
  refreshListingLifecycle: () => void
  canManageListing: (listing: Listing) => boolean
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
  storageError: string | null
  clearStorageError: () => void
}

const AppContext = createContext<AppState | null>(null)
const LISTINGS_KEY = '112233:listings:v3'
const LISTINGS_VERSION = 3

const demoUsers: DemoUser[] = [
  { id: 'tenant-demo', name: 'Lucía Demo', email: 'inquilina@112233.es', password: 'demo112233', role: 'tenant', phone: '+34 600 000 112', whatsapp: '+34 600 000 112', telegram: '@lucia_demo', about: 'Busco una habitación tranquila en Tenerife.', initials: 'LD', showPhone: true, showWhatsApp: true, allowContactForm: true, allowMessaging: true },
  { id: 'host-demo', name: 'Carlos Anfitrión', email: 'anfitrion@112233.es', password: 'demo112233', role: 'host', phone: '+34 600 112 233', whatsapp: '+34 611 223 344', telegram: '@carlos_demo', about: 'Publico habitaciones con condiciones claras.', initials: 'CA', showPhone: true, showWhatsApp: true, allowContactForm: true, allowMessaging: true },
  { id: 'admin-demo', name: 'Ana Moderación', email: 'admin@112233.es', password: 'admin112233', role: 'admin', phone: '+34 600 332 211', whatsapp: '+34 600 332 211', telegram: '@ana_admin_demo', about: 'Cuenta de administración para esta demo local.', initials: 'AM', showPhone: false, showWhatsApp: false, allowContactForm: false, allowMessaging: false },
]

const isStringArray = (value: unknown): value is string[] => Array.isArray(value) && value.every((item) => typeof item === 'string')
const isScopedStringArrays = (value: unknown): value is UserScopedState<string[]> => Boolean(value) && typeof value === 'object' && Object.values(value as Record<string, unknown>).every(isStringArray)
const isSavedSearch = (value: unknown): value is SavedSearch => Boolean(value) && typeof value === 'object' && typeof (value as SavedSearch).id === 'string' && typeof (value as SavedSearch).query === 'string'
const isScopedSavedSearches = (value: unknown): value is UserScopedState<SavedSearch[]> => Boolean(value) && typeof value === 'object' && Object.values(value as Record<string, unknown>).every((items) => Array.isArray(items) && items.every(isSavedSearch))
const isListingArray = (value: unknown): value is Listing[] => Array.isArray(value) && value.every(isListingLike)

function readListings() {
  const current = readVersioned(LISTINGS_KEY, LISTINGS_VERSION, [] as Listing[], isListingArray)
  if (!current.failure && localStorage.getItem(LISTINGS_KEY)) {
    return { data: current.data.map(normalizeListing).filter((item): item is Listing => Boolean(item)) }
  }
  if (current.failure) return { data: initialListings.map((listing) => expireListing(listing)), failure: current.failure }

  const legacy = parseJson<unknown>(localStorage.getItem('112233:listings:v2'))
  if (legacy.failure) return { data: initialListings.map((listing) => expireListing(listing)), failure: legacy.failure }
  if (legacy.data !== null) {
    if (!isListingArray(legacy.data)) return { data: initialListings.map((listing) => expireListing(listing)), failure: 'corrupted' as const }
    return { data: legacy.data.map(normalizeListing).filter((item): item is Listing => Boolean(item)) }
  }
  return { data: initialListings.map((listing) => expireListing(listing)) }
}

function readScopedStrings(key: string, legacyKey: string) {
  const current = readVersioned(key, 2, {} as UserScopedState<string[]>, isScopedStringArrays)
  if (localStorage.getItem(key) && !current.failure) return current.data
  const legacy = readJson<string[]>(legacyKey, [], isStringArray)
  return legacy.data.length ? { guest: legacy.data } : {}
}

function readScopedSavedSearches() {
  const current = readVersioned('112233:saved-searches:v3', 3, {} as UserScopedState<SavedSearch[]>, isScopedSavedSearches)
  if (localStorage.getItem('112233:saved-searches:v3') && !current.failure) return current.data
  const legacy = readJson<unknown>('112233:saved-searches:v2', [])
  const items = Array.isArray(legacy.data) ? legacy.data.filter(isSavedSearch) : []
  return items.length ? { guest: items } : {}
}

function normalizeUsers(value: DemoUser[]) {
  return value.map((user) => ({
    ...user,
    showWhatsApp: user.showWhatsApp ?? user.showPhone ?? false,
    allowContactForm: user.allowContactForm ?? user.allowMessaging ?? true,
  }))
}

const storageMessage = (failure: StorageFailure) => failure === 'quota'
  ? 'No hay espacio suficiente. Tus últimos cambios no se han guardado.'
  : failure === 'corrupted'
    ? 'Había datos locales dañados. Se ha cargado una copia segura.'
    : 'No se pudo guardar en este navegador. Revisa la privacidad o el espacio disponible.'

export function AppProvider({ children }: { children: ReactNode }) {
  const [listingLoad] = useState(readListings)
  const [rentalMode, setRentalMode] = useState<RentalMode>('long')
  const [query, setQuery] = useState('Tenerife')
  const [favoriteScopes, setFavoriteScopes] = useState<UserScopedState<string[]>>(() => readScopedStrings('112233:favorites:v2', '112233:favorites:v1'))
  const [discardedScopes, setDiscardedScopes] = useState<UserScopedState<string[]>>(() => readScopedStrings('112233:discarded:v2', '112233:discarded:v1'))
  const [filters, setFilters] = useState<Filters>({ ...defaultFilters })
  const [historyScopes, setHistoryScopes] = useState<UserScopedState<string[]>>(() => readScopedStrings('112233:search-history:v2', '112233:search-history:v1'))
  const [savedSearchScopes, setSavedSearchScopes] = useState<UserScopedState<SavedSearch[]>>(readScopedSavedSearches)
  const [mapPolygon, setMapPolygonState] = useState<MapPolygonPoint[]>(() => readJson<MapPolygonPoint[]>('112233:map-polygon:v1', []).data)
  const [allListings, setAllListings] = useState<Listing[]>(listingLoad.data)
  const [reports, setReports] = useState<ReportRecord[]>(() => readJson<ReportRecord[]>('112233:reports:v1', []).data)
  const [users, setUsers] = useState<DemoUser[]>(() => normalizeUsers(readJson<DemoUser[]>('112233:users:v1', demoUsers).data))
  const [currentUserId, setCurrentUserId] = useState<string | null>(() => readJson<string | null>('112233:session:v1', null).data)
  const [storageError, setStorageError] = useState<string | null>(() => listingLoad.failure ? storageMessage(listingLoad.failure) : null)

  const currentUser = users.find((user) => user.id === currentUserId) ?? null
  const scopeKey = currentUserId ?? 'guest'
  const favorites = useMemo(() => new Set(favoriteScopes[scopeKey] ?? []), [favoriteScopes, scopeKey])
  const discarded = useMemo(() => new Set(discardedScopes[scopeKey] ?? []), [discardedScopes, scopeKey])
  const searchHistory = useMemo(() => historyScopes[scopeKey] ?? [], [historyScopes, scopeKey])
  const savedSearches = useMemo(() => savedSearchScopes[scopeKey] ?? [], [savedSearchScopes, scopeKey])

  useEffect(() => {
    if (rentalMode !== 'holiday') return
    setFilters((current) => ({
      ...current,
      minPrice: Math.min(current.minPrice, 300),
      maxPrice: Math.min(current.maxPrice, 300),
    }))
  }, [rentalMode])

  const reportStorageFailure = useCallback((failure: StorageFailure | null) => {
    if (!failure) return
    const message = storageMessage(failure)
    setStorageError(message)
    toast.error(message, { id: 'storage-error' })
  }, [])

  useEffect(() => reportStorageFailure(persistVersioned('112233:favorites:v2', 2, favoriteScopes)), [favoriteScopes, reportStorageFailure])
  useEffect(() => reportStorageFailure(persistVersioned('112233:discarded:v2', 2, discardedScopes)), [discardedScopes, reportStorageFailure])
  useEffect(() => reportStorageFailure(persistVersioned('112233:search-history:v2', 2, historyScopes)), [historyScopes, reportStorageFailure])
  useEffect(() => reportStorageFailure(persistVersioned('112233:saved-searches:v3', 3, savedSearchScopes)), [savedSearchScopes, reportStorageFailure])
  useEffect(() => reportStorageFailure(persistJson('112233:map-polygon:v1', mapPolygon)), [mapPolygon, reportStorageFailure])
  useEffect(() => reportStorageFailure(persistVersioned(LISTINGS_KEY, LISTINGS_VERSION, allListings)), [allListings, reportStorageFailure])
  useEffect(() => reportStorageFailure(persistJson('112233:reports:v1', reports)), [reports, reportStorageFailure])
  useEffect(() => reportStorageFailure(persistJson('112233:users:v1', users)), [users, reportStorageFailure])
  useEffect(() => reportStorageFailure(persistJson('112233:session:v1', currentUserId)), [currentUserId, reportStorageFailure])

  const updateScope = useCallback(<T,>(setter: React.Dispatch<React.SetStateAction<UserScopedState<T>>>, update: (current: T | undefined) => T) => {
    setter((current) => ({ ...current, [scopeKey]: update(current[scopeKey]) }))
  }, [scopeKey])

  const toggleFavorite = useCallback((id: string) => updateScope(setFavoriteScopes, (current) => {
    const next = new Set(current ?? [])
    const wasSaved = next.has(id)
    if (wasSaved) next.delete(id); else next.add(id)
    toast.success(wasSaved ? 'Eliminado de favoritos' : 'Guardado en favoritos')
    return [...next]
  }), [updateScope])
  const discardListing = useCallback((id: string) => updateScope(setDiscardedScopes, (current) => [...new Set([...(current ?? []), id])]), [updateScope])
  const restoreDiscarded = useCallback(() => updateScope<string[]>(setDiscardedScopes, () => []), [updateScope])
  const resetFilters = useCallback(() => setFilters({ ...defaultFilters }), [])
  const addSearchHistory = useCallback((nextQuery: string) => updateScope(setHistoryScopes, (current) => {
    const normalized = nextQuery.trim()
    if (!normalized) return current ?? []
    return [normalized, ...(current ?? []).filter((item) => item.toLocaleLowerCase() !== normalized.toLocaleLowerCase())].slice(0, 8)
  }), [updateScope])
  const clearSearchHistory = useCallback(() => updateScope<string[]>(setHistoryScopes, () => []), [updateScope])
  const saveCurrentSearch = useCallback(() => updateScope(setSavedSearchScopes, (current) => {
    const searches = current ?? []
    const duplicate = searches.some((item) => item.query === query && item.rentalMode === rentalMode && JSON.stringify(item.filters) === JSON.stringify(filters) && JSON.stringify(item.polygon) === JSON.stringify(mapPolygon))
    if (duplicate) { toast.info('Esta búsqueda ya está guardada'); return searches }
    toast.success('Búsqueda guardada. Te avisaremos de nuevos anuncios.')
    return [{ id: `search-${Date.now()}`, query, rentalMode, filters: { ...filters }, alerts: true, createdAt: new Date().toISOString(), polygon: mapPolygon }, ...searches]
  }), [filters, mapPolygon, query, rentalMode, updateScope])
  const restoreSavedSearch = useCallback((id: string) => {
    const found = savedSearches.find((item) => item.id === id)
    if (found) { setQuery(found.query); setRentalMode(found.rentalMode); setFilters({ ...defaultFilters, ...found.filters }); setMapPolygonState(found.polygon ?? []) }
    return found
  }, [savedSearches])
  const removeSavedSearch = useCallback((id: string) => updateScope(setSavedSearchScopes, (current) => (current ?? []).filter((item) => item.id !== id)), [updateScope])
  const toggleSearchAlerts = useCallback((id: string) => updateScope(setSavedSearchScopes, (current) => (current ?? []).map((item) => item.id === id ? { ...item, alerts: !item.alerts } : item)), [updateScope])
  const setMapPolygon = useCallback((points: MapPolygonPoint[]) => setMapPolygonState(points), [])
  const clearMapPolygon = useCallback(() => setMapPolygonState([]), [])

  const canManageListing = useCallback((listing: Listing) => Boolean(currentUser && (currentUser.role === 'admin' || (currentUser.role === 'host' && listing.ownerUserId === currentUser.id))), [currentUser])
  const createListing = useCallback((listing: Listing) => {
    if (!currentUser || currentUser.role === 'tenant') { toast.error('Necesitas una cuenta de anfitrión para publicar.'); return }
    setAllListings((current) => [{ ...listing, ownerUserId: currentUser.id, userCreated: true }, ...current])
    toast.success('Anuncio publicado y guardado en Mis anuncios')
  }, [currentUser])
  const mutateOwned = useCallback((id: string, mutate: (listing: Listing) => Listing | null) => setAllListings((current) => current.flatMap((listing) => {
    if (listing.id !== id) return [listing]
    if (!canManageListing(listing)) { toast.error('No puedes gestionar un anuncio de otra cuenta.'); return [listing] }
    const next = mutate(listing)
    return next ? [next] : []
  })), [canManageListing])
  const updateListing = useCallback((id: string, listing: Listing) => mutateOwned(id, (current) => ({ ...listing, id: current.id, ownerUserId: current.ownerUserId })), [mutateOwned])
  const deleteListing = useCallback((id: string) => mutateOwned(id, () => null), [mutateOwned])
  const setListingStatus = useCallback((id: string, status: ListingStatus) => mutateOwned(id, (listing) => ({ ...listing, status, closedReason: status === 'Finalizado' ? listing.closedReason : undefined })), [mutateOwned])
  const renewListing = useCallback((id: string) => mutateOwned(id, (listing) => {
    const today = new Date(); today.setHours(0, 0, 0, 0)
    const currentExpiry = new Date(`${listing.expiresAt}T00:00:00`)
    const base = Number.isFinite(currentExpiry.getTime()) && currentExpiry > today ? currentExpiry : today
    base.setDate(base.getDate() + 30)
    return { ...listing, expiresAt: base.toISOString().slice(0, 10), status: 'Publicado', closedReason: undefined }
  }), [mutateOwned])
  const closeListing = useCallback((id: string) => mutateOwned(id, (listing) => ({ ...listing, status: 'Finalizado', closedReason: 'owner' })), [mutateOwned])
  const refreshListingLifecycle = useCallback(() => setAllListings((current) => current.map((listing) => expireListing(listing))), [])
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
    const user: DemoUser = { id: `user-${Date.now()}`, ...input, phone: '', whatsapp: '', telegram: '', about: '', initials, showPhone: false, showWhatsApp: false, allowContactForm: true, allowMessaging: true }
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
  const value = useMemo<AppState>(() => ({ rentalMode, setRentalMode, query, setQuery, favorites, toggleFavorite, discarded, discardListing, restoreDiscarded, filters, setFilters, resetFilters, activeFilterCount, searchHistory, addSearchHistory, clearSearchHistory, savedSearches, saveCurrentSearch, restoreSavedSearch, removeSavedSearch, toggleSearchAlerts, mapPolygon, setMapPolygon, clearMapPolygon, allListings, createListing, updateListing, deleteListing, setListingStatus, renewListing, closeListing, refreshListingLifecycle, canManageListing, reports, addReport, users, currentUser, login, register, logout, updateProfile, deleteAccount, toggleUserBlocked, storageError, clearStorageError: () => setStorageError(null) }), [rentalMode, query, favorites, toggleFavorite, discarded, discardListing, restoreDiscarded, filters, resetFilters, activeFilterCount, searchHistory, addSearchHistory, clearSearchHistory, savedSearches, saveCurrentSearch, restoreSavedSearch, removeSavedSearch, toggleSearchAlerts, mapPolygon, setMapPolygon, clearMapPolygon, allListings, createListing, updateListing, deleteListing, setListingStatus, renewListing, closeListing, refreshListingLifecycle, canManageListing, reports, addReport, users, currentUser, login, register, logout, updateProfile, deleteAccount, toggleUserBlocked, storageError])
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) throw new Error('useApp debe usarse dentro de AppProvider')
  return context
}
