import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { hydrateSession, loginWithPassword, logoutSession, registerAccount } from '@/api/auth'
import { getAdminUsers, moderateRemoteListing, setRemoteUserBlocked } from '@/api/admin'
import { ApiError } from '@/api/client'
import { addDiscarded, addFavorite, clearDiscarded, createSavedSearch, deleteSavedSearch, getDiscarded, getFavorites, getSavedSearches, importGuestState, removeFavorite, updateSavedSearch } from '@/api/user-state'
import { deleteCurrentUser, updateCurrentUser } from '@/api/users'
import { addSearchHistory as addRemoteSearchHistory, clearSearchHistory as clearRemoteSearchHistory, getSearchHistory } from '@/api/search-history'
import { createRemoteListing, deleteRemoteListing, getPublicListings, renewRemoteListing, setRemoteListingStatus, updateRemoteListing } from '@/api/listings'
import { syncListingImages } from '@/api/media'
import { getRemoteThreads, sendRemoteMessage, type RemoteThread } from '@/api/messages'
import { createRemoteReport, getRemoteReports } from '@/api/reports'
import { defaultFilters, initialListings } from '@/data/listings'
import { expireListing, isListingLike, normalizeListing } from '@/lib/listings'
import { getActiveFilterKeys, normalizeFilters } from '@/lib/search'
import { isSupportedTenerifeQuery, resolveTenerifeLocation, sanitizeTenerifeHistory } from '@/lib/tenerife'
import { cleanupOrphanedMedia, isMediaReference, removeUnusedMediaReferences } from '@/lib/media-storage'
import { parseJson, persistJson, persistVersioned, readJson, readVersioned, type StorageFailure } from '@/lib/storage'
import type { DemoUser, Filters, Listing, ListingStatus, LocalListingComment, LocalMessageThread, MapPolygonPoint, RentalMode, ReportRecord, UserRole } from '@/types'

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
  createListing: (listing: Listing) => Promise<boolean>
  updateListing: (id: string, listing: Listing) => Promise<boolean>
  deleteListing: (id: string) => void
  setListingStatus: (id: string, status: ListingStatus) => void
  renewListing: (id: string) => void
  closeListing: (id: string) => void
  refreshListingLifecycle: () => void
  canManageListing: (listing: Listing) => boolean
  reports: ReportRecord[]
  addReport: (listingId: string, reason: string, comment: string) => void
  localThreads: LocalMessageThread[]
  addLocalMessage: (thread: Omit<LocalMessageThread, 'id' | 'createdAt' | 'status'> & { body?: string }) => Promise<boolean>
  localComments: LocalListingComment[]
  addLocalComment: (listingId: string, text: string) => void
  updateLocalComment: (id: string, text: string) => void
  deleteLocalComment: (id: string) => void
  users: DemoUser[]
  currentUser: DemoUser | null
  login: (email: string, password: string) => Promise<string | null>
  register: (input: RegisterInput) => Promise<string | null>
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
const DRAFT_KEY = '112233:listing-draft:v3'
const LEGACY_DRAFT_KEY = '112233:listing-draft:v2'

function collectMediaReferences(value: unknown, found = new Set<string>()) {
  if (typeof value === 'string') {
    if (isMediaReference(value)) found.add(value)
    return found
  }
  if (Array.isArray(value)) value.forEach((item) => collectMediaReferences(item, found))
  else if (value && typeof value === 'object') Object.values(value as Record<string, unknown>).forEach((item) => collectMediaReferences(item, found))
  return found
}

function readDraftRecord() {
  for (const key of [DRAFT_KEY, LEGACY_DRAFT_KEY]) {
    const parsed = parseJson<Record<string, unknown>>(localStorage.getItem(key))
    if (parsed.data) return { key, value: parsed.data }
  }
  return null
}

function usedMediaReferences(listings: Listing[], users: DemoUser[], draft: unknown = readDraftRecord()?.value) {
  return collectMediaReferences([listings, users, draft])
}

type RemoteUser = Omit<DemoUser, 'password'>

function toAppUser(user: RemoteUser): DemoUser {
  return { ...user, password: '', allowMessaging: user.allowContactForm, blocked: false }
}

function toLocalThread(thread: RemoteThread, listings: Listing[], currentUserId: string): LocalMessageThread | null {
  const listing = listings.find((item) => item.id === thread.listingId)
  if (!listing) return null
  return {
    id: thread.id,
    listingId: thread.listingId,
    listingTitle: listing.title,
    imageRef: listing.images[0] ?? '',
    contactName: thread.hostId === currentUserId ? 'Inquilino' : listing.owner.name,
    messagePreview: thread.lastMessagePreview ?? 'Sin mensajes',
    createdAt: thread.lastMessageAt,
    status: 'Enviado',
  }
}

const isStringArray = (value: unknown): value is string[] => Array.isArray(value) && value.every((item) => typeof item === 'string')
const isScopedStringArrays = (value: unknown): value is UserScopedState<string[]> => Boolean(value) && typeof value === 'object' && Object.values(value as Record<string, unknown>).every(isStringArray)
const isSavedSearch = (value: unknown): value is SavedSearch => Boolean(value) && typeof value === 'object' && typeof (value as SavedSearch).id === 'string' && typeof (value as SavedSearch).query === 'string'
const isScopedSavedSearches = (value: unknown): value is UserScopedState<SavedSearch[]> => Boolean(value) && typeof value === 'object' && Object.values(value as Record<string, unknown>).every((items) => Array.isArray(items) && items.every(isSavedSearch))
const isLocalThread = (value: unknown): value is LocalMessageThread => Boolean(value) && typeof value === 'object' && typeof (value as LocalMessageThread).listingId === 'string' && typeof (value as LocalMessageThread).messagePreview === 'string'
const isScopedLocalThreads = (value: unknown): value is UserScopedState<LocalMessageThread[]> => Boolean(value) && typeof value === 'object' && Object.values(value as Record<string, unknown>).every((items) => Array.isArray(items) && items.every(isLocalThread))
const isLocalComment = (value: unknown): value is LocalListingComment => Boolean(value) && typeof value === 'object' && typeof (value as LocalListingComment).id === 'string' && typeof (value as LocalListingComment).userId === 'string' && typeof (value as LocalListingComment).listingId === 'string' && typeof (value as LocalListingComment).text === 'string' && typeof (value as LocalListingComment).createdAt === 'string'
const isScopedLocalComments = (value: unknown): value is UserScopedState<LocalListingComment[]> => Boolean(value) && typeof value === 'object' && Object.values(value as Record<string, unknown>).every((items) => Array.isArray(items) && items.every(isLocalComment))
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
  if (localStorage.getItem(key) && !current.failure) {
    if (key === '112233:search-history:v2') return Object.fromEntries(Object.entries(current.data).map(([scope, values]) => [scope, sanitizeTenerifeHistory(values)]))
    return current.data
  }
  const legacy = readJson<string[]>(legacyKey, [], isStringArray)
  return legacy.data.length ? { guest: key === '112233:search-history:v2' ? sanitizeTenerifeHistory(legacy.data) : legacy.data } : {}
}

function readScopedLocalThreads() {
  return readVersioned('112233:message-threads:v1', 1, {} as UserScopedState<LocalMessageThread[]>, isScopedLocalThreads).data
}

function readScopedLocalComments() {
  return readVersioned('112233:listing-comments:v1', 1, {} as UserScopedState<LocalListingComment[]>, isScopedLocalComments).data
}

function readScopedSavedSearches() {
  const current = readVersioned('112233:saved-searches:v3', 3, {} as UserScopedState<SavedSearch[]>, isScopedSavedSearches)
  if (localStorage.getItem('112233:saved-searches:v3') && !current.failure) {
    return Object.fromEntries(Object.entries(current.data).map(([scope, items]) => [scope, items.map((item) => ({ ...item, filters: normalizeFilters(item.filters) }))]))
  }
  const legacy = readJson<unknown>('112233:saved-searches:v2', [])
  const items = Array.isArray(legacy.data) ? legacy.data.filter(isSavedSearch) : []
  return items.length ? { guest: items.map((item) => ({ ...item, filters: normalizeFilters(item.filters) })) } : {}
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
  const [mapPolygon, setMapPolygonState] = useState<MapPolygonPoint[]>([])
  const [allListings, setAllListings] = useState<Listing[]>(listingLoad.data)
  const [reports, setReports] = useState<ReportRecord[]>(() => readJson<ReportRecord[]>('112233:reports:v1', []).data)
  const [threadScopes, setThreadScopes] = useState<UserScopedState<LocalMessageThread[]>>(readScopedLocalThreads)
  const [commentScopes, setCommentScopes] = useState<UserScopedState<LocalListingComment[]>>(readScopedLocalComments)
  const [users, setUsers] = useState<DemoUser[]>([])
  const [currentUserId, setCurrentUserId] = useState<string | null>(null)
  const [storageError, setStorageError] = useState<string | null>(() => listingLoad.failure ? storageMessage(listingLoad.failure) : null)
  const orphanCleanupStarted = useRef(false)
  const authHydrationStarted = useRef(false)
  const listingsHydrationStarted = useRef(false)

  const currentUser = users.find((user) => user.id === currentUserId) ?? null
  const scopeKey = currentUserId ?? 'guest'
  const favorites = useMemo(() => new Set(favoriteScopes[scopeKey] ?? []), [favoriteScopes, scopeKey])
  const discarded = useMemo(() => new Set(discardedScopes[scopeKey] ?? []), [discardedScopes, scopeKey])
  const searchHistory = useMemo(() => historyScopes[scopeKey] ?? [], [historyScopes, scopeKey])
  const savedSearches = useMemo(() => savedSearchScopes[scopeKey] ?? [], [savedSearchScopes, scopeKey])
  const localThreads = useMemo(() => threadScopes[scopeKey] ?? [], [scopeKey, threadScopes])
  const localComments = useMemo(() => commentScopes[scopeKey] ?? [], [commentScopes, scopeKey])

  useEffect(() => {
    if (rentalMode !== 'holiday') return
    setFilters((current) => ({
      ...current,
      minPrice: Math.min(current.minPrice, 350),
      maxPrice: Math.min(current.maxPrice, 350),
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
  useEffect(() => reportStorageFailure(persistVersioned(LISTINGS_KEY, LISTINGS_VERSION, allListings)), [allListings, reportStorageFailure])
  useEffect(() => reportStorageFailure(persistJson('112233:reports:v1', reports)), [reports, reportStorageFailure])
  useEffect(() => reportStorageFailure(persistVersioned('112233:message-threads:v1', 1, threadScopes)), [threadScopes, reportStorageFailure])
  useEffect(() => reportStorageFailure(persistVersioned('112233:listing-comments:v1', 1, commentScopes)), [commentScopes, reportStorageFailure])
  useEffect(() => {
    if (orphanCleanupStarted.current) return
    orphanCleanupStarted.current = true
    void cleanupOrphanedMedia(usedMediaReferences(allListings, users)).catch(() => undefined)
  }, [allListings, users])

  const setRemoteUser = useCallback((remote: RemoteUser) => {
    const user = toAppUser(remote)
    setUsers((current) => [...current.filter((item) => item.id !== user.id), user])
    setCurrentUserId(user.id)
  }, [])

  useEffect(() => {
    if (authHydrationStarted.current) return
    authHydrationStarted.current = true
    void hydrateSession().then((user) => { if (user) setRemoteUser(user) }).catch((error: unknown) => {
      if (!(error instanceof ApiError) || error.status !== 401) toast.error('No se pudo restaurar la sesión.')
    })
  }, [setRemoteUser])

  useEffect(() => {
    if (listingsHydrationStarted.current) return
    listingsHydrationStarted.current = true
    void getPublicListings().then(setAllListings).catch(() => {
      toast.error('No se pudo cargar el catálogo del servidor. Se muestra la copia local.')
    })
  }, [])

  useEffect(() => {
    if (!currentUserId) return
    const guestFavorites = (favoriteScopes.guest ?? []).filter((id) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id))
    const guestSavedSearches = (savedSearchScopes.guest ?? []).map((search) => ({
      name: search.query,
      query: search.query,
      rentalMode: search.rentalMode,
      filters: search.filters as unknown as Record<string, unknown>,
      polygon: search.polygon,
      alertsEnabled: search.alerts,
    }))
    void importGuestState({ favoriteIds: guestFavorites, savedSearches: guestSavedSearches }).then(() =>
      Promise.all([getFavorites(), getDiscarded(), getSavedSearches()]),
    ).then(([remoteFavorites, remoteDiscarded, remoteSearches]) => {
      setFavoriteScopes((current) => ({ ...current, [currentUserId]: remoteFavorites }))
      setDiscardedScopes((current) => ({ ...current, [currentUserId]: remoteDiscarded }))
      setSavedSearchScopes((current) => ({
        ...current,
        [currentUserId]: remoteSearches.map((search) => ({
          id: search.id,
          query: search.query,
          rentalMode: search.rentalMode,
          filters: normalizeFilters({ ...defaultFilters, ...search.filters }),
          alerts: search.alertsEnabled,
          createdAt: search.createdAt,
          polygon: search.polygon,
        })),
      }))
    }).catch(() => toast.error('No se pudieron sincronizar los datos de tu cuenta.'))
  }, [currentUserId, favoriteScopes.guest, savedSearchScopes.guest])

  useEffect(() => {
    if (!currentUserId) return
    void getSearchHistory().then((history) => {
      setHistoryScopes((current) => ({ ...current, [currentUserId]: sanitizeTenerifeHistory(history) }))
    }).catch(() => toast.error('No se pudo sincronizar el historial de búsqueda.'))
  }, [currentUserId])

  useEffect(() => {
    if (!currentUserId) return
    void getRemoteThreads().then((threads) => {
      const remote = threads.map((thread) => toLocalThread(thread, allListings, currentUserId)).filter((thread): thread is LocalMessageThread => Boolean(thread))
      setThreadScopes((current) => ({ ...current, [currentUserId]: remote }))
    }).catch(() => toast.error('No se pudieron cargar los mensajes.'))
  }, [allListings, currentUserId])

  useEffect(() => {
    if (currentUser?.role !== 'admin') return
    void getRemoteReports().then(setReports).catch(() => toast.error('No se pudieron cargar las denuncias.'))
  }, [currentUser?.role])

  useEffect(() => {
    if (currentUser?.role !== 'admin') return
    void getAdminUsers().then(setUsers).catch(() => toast.error('No se pudieron cargar los usuarios.'))
  }, [currentUser?.role])

  const updateScope = useCallback(<T,>(setter: React.Dispatch<React.SetStateAction<UserScopedState<T>>>, update: (current: T | undefined) => T) => {
    setter((current) => ({ ...current, [scopeKey]: update(current[scopeKey]) }))
  }, [scopeKey])

  const toggleFavorite = useCallback((id: string) => updateScope(setFavoriteScopes, (current) => {
    const next = new Set(current ?? [])
    const wasSaved = next.has(id)
    if (wasSaved) next.delete(id); else next.add(id)
    if (currentUserId) {
      const operation = wasSaved ? removeFavorite(id) : addFavorite(id)
      void operation.catch(() => {
        updateScope(setFavoriteScopes, (latest) => wasSaved ? [...new Set([...(latest ?? []), id])] : (latest ?? []).filter((item) => item !== id))
        toast.error('No se pudo sincronizar el favorito.')
      })
    }
    toast.success(wasSaved ? 'Eliminado de favoritos' : 'Guardado en favoritos')
    return [...next]
  }), [currentUserId, updateScope])
  const discardListing = useCallback((id: string) => updateScope(setDiscardedScopes, (current) => {
    if (currentUserId) void addDiscarded(id).catch(() => toast.error('No se pudo sincronizar el anuncio oculto.'))
    return [...new Set([...(current ?? []), id])]
  }), [currentUserId, updateScope])
  const restoreDiscarded = useCallback(() => updateScope<string[]>(setDiscardedScopes, () => {
    if (currentUserId) void clearDiscarded().catch(() => toast.error('No se pudieron restaurar los anuncios.'))
    return []
  }), [currentUserId, updateScope])
  const resetFilters = useCallback(() => setFilters({ ...defaultFilters }), [])
  const addSearchHistory = useCallback((nextQuery: string) => updateScope(setHistoryScopes, (current) => {
    const location = resolveTenerifeLocation(nextQuery)
    if (!location || !isSupportedTenerifeQuery(nextQuery)) return sanitizeTenerifeHistory(current ?? [])
    if (currentUserId) void addRemoteSearchHistory(location.normalizedValue).catch(() => toast.error('No se pudo guardar el historial de búsqueda.'))
    return sanitizeTenerifeHistory([location.normalizedValue, ...(current ?? [])])
  }), [currentUserId, updateScope])
  const clearSearchHistory = useCallback(() => updateScope<string[]>(setHistoryScopes, () => {
    if (currentUserId) void clearRemoteSearchHistory().catch(() => toast.error('No se pudo borrar el historial de búsqueda.'))
    return []
  }), [currentUserId, updateScope])
  const saveCurrentSearch = useCallback(() => updateScope(setSavedSearchScopes, (current) => {
    const searches = current ?? []
    const duplicate = searches.some((item) => item.query === query && item.rentalMode === rentalMode && JSON.stringify(item.filters) === JSON.stringify(filters) && JSON.stringify(item.polygon) === JSON.stringify(mapPolygon))
    if (duplicate) { toast.info('Esta búsqueda ya está guardada'); return searches }
    const optimistic = { id: `search-${Date.now()}`, query, rentalMode, filters: { ...filters }, alerts: true, createdAt: new Date().toISOString(), polygon: mapPolygon }
    if (currentUserId) {
      void createSavedSearch({ name: query, query, rentalMode, filters: filters as unknown as Record<string, unknown>, polygon: mapPolygon, alertsEnabled: true }).then((saved) => {
        updateScope(setSavedSearchScopes, (latest) => (latest ?? []).map((item) => item.id === optimistic.id ? { ...item, id: saved.id, createdAt: saved.createdAt } : item))
      }).catch(() => {
        updateScope(setSavedSearchScopes, (latest) => (latest ?? []).filter((item) => item.id !== optimistic.id))
        toast.error('No se pudo guardar la búsqueda.')
      })
    }
    toast.success('Búsqueda guardada. Te avisaremos de nuevos anuncios.')
    return [optimistic, ...searches]
  }), [currentUserId, filters, mapPolygon, query, rentalMode, updateScope])
  const restoreSavedSearch = useCallback((id: string) => {
    const found = savedSearches.find((item) => item.id === id)
    if (found) { setQuery(found.query); setRentalMode(found.rentalMode); setFilters(normalizeFilters(found.filters)); setMapPolygonState(found.polygon ?? []) }
    return found
  }, [savedSearches])
  const removeSavedSearch = useCallback((id: string) => updateScope(setSavedSearchScopes, (current) => {
    if (currentUserId) void deleteSavedSearch(id).catch(() => toast.error('No se pudo eliminar la búsqueda.'))
    return (current ?? []).filter((item) => item.id !== id)
  }), [currentUserId, updateScope])
  const toggleSearchAlerts = useCallback((id: string) => updateScope(setSavedSearchScopes, (current) => {
    const search = (current ?? []).find((item) => item.id === id)
    if (currentUserId && search) void updateSavedSearch(id, { alertsEnabled: !search.alerts }).catch(() => toast.error('No se pudieron actualizar las alertas.'))
    return (current ?? []).map((item) => item.id === id ? { ...item, alerts: !item.alerts } : item)
  }), [currentUserId, updateScope])
  const setMapPolygon = useCallback((points: MapPolygonPoint[]) => setMapPolygonState(points), [])
  const clearMapPolygon = useCallback(() => setMapPolygonState([]), [])

  const canManageListing = useCallback((listing: Listing) => Boolean(currentUser && (currentUser.role === 'admin' || (currentUser.role === 'host' && listing.ownerUserId === currentUser.id))), [currentUser])
  const createListing = useCallback(async (listing: Listing) => {
    if (!currentUser || currentUser.role === 'tenant') { toast.error('Necesitas una cuenta de anfitrión para publicar.'); return false }
    const optimistic = { ...listing, ownerUserId: currentUser.id, userCreated: true }
    setAllListings((current) => [optimistic, ...current])
    try {
      const remote = await createRemoteListing(optimistic)
      let stored = { ...remote, userCreated: true }
      try {
        const images = await syncListingImages(remote.id, optimistic.images)
        stored = { ...stored, images }
        await removeUnusedMediaReferences(optimistic.images, images)
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'El anuncio se guardó, pero no se pudieron subir las imágenes.')
      }
      setAllListings((current) => current.map((item) => item.id === optimistic.id ? stored : item))
      toast.success('Anuncio enviado a moderación y guardado en Mis anuncios')
      return true
    } catch {
      setAllListings((current) => current.filter((item) => item.id !== optimistic.id))
      toast.error('No se pudo publicar el anuncio en el servidor.')
      return false
    }
  }, [currentUser])
  const mutateOwned = useCallback((id: string, mutate: (listing: Listing) => Listing | null) => setAllListings((current) => current.flatMap((listing) => {
    if (listing.id !== id) return [listing]
    if (!canManageListing(listing)) { toast.error('No puedes gestionar un anuncio de otra cuenta.'); return [listing] }
    const next = mutate(listing)
    return next ? [next] : []
  })), [canManageListing])
  const updateListing = useCallback(async (id: string, listing: Listing) => {
    const previous = allListings.find((item) => item.id === id)
    if (!previous || !canManageListing(previous)) {
      if (previous) toast.error('No puedes gestionar un anuncio de otra cuenta.')
      return false
    }
    const next = { ...listing, id: previous.id, ownerUserId: previous.ownerUserId }
    setAllListings((current) => current.map((item) => item.id === id ? next : item))
    try {
      const remote = await updateRemoteListing(id, next)
      let stored = { ...remote, userCreated: true }
      try {
        const images = await syncListingImages(id, next.images)
        stored = { ...stored, images }
        await removeUnusedMediaReferences(next.images, images)
      } catch (error) {
        toast.error(error instanceof Error ? error.message : 'No se pudieron actualizar las imágenes del anuncio.')
      }
      setAllListings((current) => current.map((item) => item.id === id ? stored : item))
      return true
    } catch {
      setAllListings((current) => current.map((item) => item.id === id ? previous : item))
      toast.error('No se pudieron guardar los cambios del anuncio.')
      return false
    }
  }, [allListings, canManageListing])
  const deleteListing = useCallback((id: string) => {
    const listing = allListings.find((item) => item.id === id)
    if (!listing) return
    if (!canManageListing(listing)) {
      toast.error('No puedes gestionar un anuncio de otra cuenta.')
      return
    }
    const remaining = allListings.filter((item) => item.id !== id)
    const draftRecord = readDraftRecord()
    const deleteDraft = draftRecord?.value.listingId === id
    const draftMedia = deleteDraft ? collectMediaReferences(draftRecord?.value) : new Set<string>()
    if (deleteDraft) {
      localStorage.removeItem(DRAFT_KEY)
      localStorage.removeItem(LEGACY_DRAFT_KEY)
    }
    setAllListings(remaining)
    void deleteRemoteListing(id).catch(() => {
      setAllListings((current) => [listing, ...current])
      toast.error('No se pudo eliminar el anuncio en el servidor.')
    })
    void removeUnusedMediaReferences([...listing.images, ...draftMedia], usedMediaReferences(remaining, users, deleteDraft ? null : draftRecord?.value)).catch((error) =>
      toast.error(error instanceof Error ? error.message : 'No se pudieron limpiar las imágenes locales.'),
    )
  }, [allListings, canManageListing, users])
  const setListingStatus = useCallback((id: string, status: ListingStatus) => {
    const previous = allListings.find((listing) => listing.id === id)
    if (!previous || !canManageListing(previous)) return
    mutateOwned(id, (listing) => ({ ...listing, status, closedReason: status === 'Finalizado' ? listing.closedReason : undefined }))
    if (currentUser?.role === 'admin' && previous) {
      void moderateRemoteListing(id, status).catch(() => {
        setAllListings((current) => current.map((listing) => listing.id === id ? previous : listing))
        toast.error('No se pudo moderar el anuncio en el servidor.')
      })
    } else {
      void setRemoteListingStatus(id, status).then((remote) => {
        setAllListings((current) => current.map((listing) => listing.id === id ? { ...remote, userCreated: true } : listing))
      }).catch(() => {
        setAllListings((current) => current.map((listing) => listing.id === id ? previous : listing))
        toast.error('No se pudo actualizar el estado del anuncio en el servidor.')
      })
    }
  }, [allListings, canManageListing, currentUser?.role, mutateOwned])
  const renewListing = useCallback((id: string) => {
    const previous = allListings.find((listing) => listing.id === id)
    if (!previous || !canManageListing(previous)) return
    mutateOwned(id, (listing) => {
    const today = new Date(); today.setHours(0, 0, 0, 0)
    const currentExpiry = new Date(`${listing.expiresAt}T00:00:00`)
    const base = Number.isFinite(currentExpiry.getTime()) && currentExpiry > today ? currentExpiry : today
    base.setDate(base.getDate() + 30)
    return { ...listing, expiresAt: base.toISOString().slice(0, 10), closedReason: undefined }
    })
    void renewRemoteListing(id).then((remote) => {
      setAllListings((current) => current.map((listing) => listing.id === id ? { ...remote, userCreated: true } : listing))
    }).catch(() => {
      setAllListings((current) => current.map((listing) => listing.id === id ? previous : listing))
      toast.error('No se pudo renovar el anuncio en el servidor.')
    })
  }, [allListings, canManageListing, mutateOwned])
  const closeListing = useCallback((id: string) => setListingStatus(id, 'Finalizado'), [setListingStatus])
  const refreshListingLifecycle = useCallback(() => setAllListings((current) => current.map((listing) => expireListing(listing))), [])
  const addReport = useCallback((listingId: string, reason: string, comment: string) => {
    const optimistic: ReportRecord = { id: `REP-${Date.now().toString().slice(-6)}`, listingId, reason, comment, createdAt: new Date().toISOString(), status: 'Abierta' }
    setReports((current) => [optimistic, ...current])
    void createRemoteReport(listingId, reason, comment).then((report) => {
      setReports((current) => current.map((item) => item.id === optimistic.id ? report : item))
    }).catch(() => {
      setReports((current) => current.filter((item) => item.id !== optimistic.id))
      toast.error('No se pudo enviar la denuncia al servidor.')
    })
  }, [])
  const addLocalMessage = useCallback(async (thread: Omit<LocalMessageThread, 'id' | 'createdAt' | 'status'> & { body?: string }) => {
    if (!currentUserId) { toast.error('Inicia sesión para enviar un mensaje.'); return false }
    const optimistic: LocalMessageThread = { ...thread, id: `local-${Date.now()}`, createdAt: new Date().toISOString(), status: 'Enviado' }
    updateScope(setThreadScopes, (current) => [optimistic, ...(current ?? [])])
    try {
      await sendRemoteMessage(thread.listingId, thread.body ?? thread.messagePreview)
      const threads = await getRemoteThreads()
      const remote = threads.map((item) => toLocalThread(item, allListings, currentUserId)).filter((item): item is LocalMessageThread => Boolean(item))
      setThreadScopes((current) => ({ ...current, [currentUserId]: remote }))
      return true
    } catch {
      updateScope(setThreadScopes, (current) => (current ?? []).filter((item) => item.id !== optimistic.id))
      toast.error('No se pudo enviar el mensaje al servidor.')
      return false
    }
  }, [allListings, currentUserId, updateScope])
  const addLocalComment = useCallback((listingId: string, text: string) => updateScope(setCommentScopes, (current) => [{ id: `comment-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, userId: scopeKey, listingId, text: text.trim(), createdAt: new Date().toISOString() }, ...(current ?? [])]), [scopeKey, updateScope])
  const updateLocalComment = useCallback((id: string, text: string) => updateScope(setCommentScopes, (current) => (current ?? []).map((comment) => comment.id === id ? { ...comment, text: text.trim(), updatedAt: new Date().toISOString() } : comment)), [updateScope])
  const deleteLocalComment = useCallback((id: string) => updateScope(setCommentScopes, (current) => (current ?? []).filter((comment) => comment.id !== id)), [updateScope])

  const login = useCallback(async (email: string, password: string) => {
    try {
      setRemoteUser(await loginWithPassword(email, password))
      return null
    } catch (error) {
      return error instanceof ApiError ? error.message : 'No se pudo iniciar sesión. Inténtalo de nuevo.'
    }
  }, [setRemoteUser])
  const register = useCallback(async (input: RegisterInput) => {
    try {
      setRemoteUser(await registerAccount(input))
      return null
    } catch (error) {
      return error instanceof ApiError ? error.message : 'No se pudo crear la cuenta. Inténtalo de nuevo.'
    }
  }, [setRemoteUser])
  const logout = useCallback(() => {
    setCurrentUserId(null)
    void logoutSession().catch(() => undefined)
  }, [])
  const updateProfile = useCallback((changes: ProfileUpdate) => {
    if (!currentUserId) return
    const previous = users.find((user) => user.id === currentUserId)
    const nextUsers = users.map((user) => user.id === currentUserId ? { ...user, ...changes } : user)
    setUsers(nextUsers)
    const serverFields = Object.fromEntries(
      Object.entries(changes).filter(([key]) => [
        'name', 'phone', 'whatsapp', 'telegram', 'about', 'showPhone', 'showWhatsApp', 'allowContactForm',
      ].includes(key)),
    )
    if (Object.keys(serverFields).length) {
      void updateCurrentUser(serverFields).then(setRemoteUser).catch(() => {
        if (previous) setUsers((current) => current.map((user) => user.id === previous.id ? previous : user))
        toast.error('No se pudo guardar el perfil en el servidor.')
      })
    }
    if (previous?.avatarRef && Object.prototype.hasOwnProperty.call(changes, 'avatarRef') && changes.avatarRef !== previous.avatarRef) {
      void removeUnusedMediaReferences([previous.avatarRef], usedMediaReferences(allListings, nextUsers)).catch((error) =>
        toast.error(error instanceof Error ? error.message : 'No se pudo limpiar el avatar anterior.'),
      )
    }
    toast.success('Perfil actualizado')
  }, [allListings, currentUserId, setRemoteUser, users])
  const deleteAccount = useCallback(() => {
    if (!currentUserId) return
    void deleteCurrentUser().catch(() => toast.error('No se pudo eliminar la cuenta en el servidor.'))
    const ownedListings = allListings.filter((listing) => listing.ownerUserId === currentUserId)
    const remainingListings = allListings.filter((listing) => listing.ownerUserId !== currentUserId)
    const remainingUsers = users.filter((user) => user.id !== currentUserId)
    const draftRecord = readDraftRecord()
    const draftOwner = draftRecord?.value.ownerUserId
    const deleteDraft = Boolean(draftRecord && (!draftOwner || draftOwner === currentUserId))
    const removedMedia = collectMediaReferences([ownedListings, users.find((user) => user.id === currentUserId), deleteDraft ? draftRecord?.value : null])
    const retainedDraft = deleteDraft ? null : draftRecord?.value
    setAllListings(remainingListings)
    setUsers(remainingUsers)
    setFavoriteScopes((current) => Object.fromEntries(Object.entries(current).filter(([scope]) => scope !== currentUserId)))
    setDiscardedScopes((current) => Object.fromEntries(Object.entries(current).filter(([scope]) => scope !== currentUserId)))
    setHistoryScopes((current) => Object.fromEntries(Object.entries(current).filter(([scope]) => scope !== currentUserId)))
    setSavedSearchScopes((current) => Object.fromEntries(Object.entries(current).filter(([scope]) => scope !== currentUserId)))
    setThreadScopes((current) => Object.fromEntries(Object.entries(current).filter(([scope]) => scope !== currentUserId)))
    setCommentScopes((current) => Object.fromEntries(Object.entries(current).filter(([scope]) => scope !== currentUserId)))
    setReports((current) => current.filter((report) => !ownedListings.some((listing) => listing.id === report.listingId)))
    if (deleteDraft) {
      localStorage.removeItem(DRAFT_KEY)
      localStorage.removeItem(LEGACY_DRAFT_KEY)
    }
    setCurrentUserId(null)
    void removeUnusedMediaReferences([...removedMedia], usedMediaReferences(remainingListings, remainingUsers, retainedDraft)).catch((error) =>
      toast.error(error instanceof Error ? error.message : 'No se pudieron limpiar todos los datos multimedia de la cuenta.'),
    )
  }, [allListings, currentUserId, users])
  const toggleUserBlocked = useCallback((id: string) => {
    if (currentUser?.role !== 'admin') return
    const previous = users.find((user) => user.id === id)
    if (!previous) return
    const blocked = !previous.blocked
    setUsers((current) => current.map((user) => user.id === id ? { ...user, blocked } : user))
    void setRemoteUserBlocked(id, blocked).catch(() => {
      setUsers((current) => current.map((user) => user.id === id ? previous : user))
      toast.error('No se pudo actualizar el estado de la cuenta.')
    })
  }, [currentUser?.role, users])

  const activeFilterCount = useMemo(() => getActiveFilterKeys(filters).length, [filters])
  const value = useMemo<AppState>(() => ({ rentalMode, setRentalMode, query, setQuery, favorites, toggleFavorite, discarded, discardListing, restoreDiscarded, filters, setFilters, resetFilters, activeFilterCount, searchHistory, addSearchHistory, clearSearchHistory, savedSearches, saveCurrentSearch, restoreSavedSearch, removeSavedSearch, toggleSearchAlerts, mapPolygon, setMapPolygon, clearMapPolygon, allListings, createListing, updateListing, deleteListing, setListingStatus, renewListing, closeListing, refreshListingLifecycle, canManageListing, reports, addReport, localThreads, addLocalMessage, localComments, addLocalComment, updateLocalComment, deleteLocalComment, users, currentUser, login, register, logout, updateProfile, deleteAccount, toggleUserBlocked, storageError, clearStorageError: () => setStorageError(null) }), [rentalMode, query, favorites, toggleFavorite, discarded, discardListing, restoreDiscarded, filters, resetFilters, activeFilterCount, searchHistory, addSearchHistory, clearSearchHistory, savedSearches, saveCurrentSearch, restoreSavedSearch, removeSavedSearch, toggleSearchAlerts, mapPolygon, setMapPolygon, clearMapPolygon, allListings, createListing, updateListing, deleteListing, setListingStatus, renewListing, closeListing, refreshListingLifecycle, canManageListing, reports, addReport, localThreads, addLocalMessage, localComments, addLocalComment, updateLocalComment, deleteLocalComment, users, currentUser, login, register, logout, updateProfile, deleteAccount, toggleUserBlocked, storageError])
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) throw new Error('useApp debe usarse dentro de AppProvider')
  return context
}
