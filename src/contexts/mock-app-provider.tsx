import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Context,
  type ReactNode,
} from 'react'
import { toast } from 'sonner'
import { defaultFilters, initialListings } from '@/data/listings'
import { expireListing, isListingLike, normalizeListing } from '@/lib/listings'
import { cleanupOrphanedMedia, isMediaReference, removeUnusedMediaReferences } from '@/lib/media-storage'
import { getActiveFilterKeys, normalizeFilters } from '@/lib/search'
import { parseJson, persistJson, persistVersioned, readJson, readVersioned, type StorageFailure } from '@/lib/storage'
import { isSupportedTenerifeQuery, resolveTenerifeLocation, sanitizeTenerifeHistory } from '@/lib/tenerife'
import type {
  DemoUser,
  Filters,
  Listing,
  ListingStatus,
  LocalListingComment,
  LocalMessageThread,
  MapPolygonPoint,
  RentalMode,
  ReportRecord,
  UserRole,
} from '@/types'
import type { AppState, SavedSearch } from '@/contexts/app-context'

const LISTINGS_KEY = '112233:listings:v3'
const LISTINGS_VERSION = 3
const DRAFT_KEY = '112233:listing-draft:v3'
const LEGACY_DRAFT_KEY = '112233:listing-draft:v2'
const USERS_KEY = '112233:users:v1'
const SESSION_KEY = '112233:session:v1'

type RegisterInput = { name: string; email: string; password: string; role: UserRole }
type ProfileUpdate = Partial<Omit<DemoUser, 'id' | 'email' | 'password' | 'role'>>
type UserScopedState<T> = Record<string, T>
type MockUser = DemoUser & { passwordHash: string }

const initialUsers: MockUser[] = [
  {
    id: 'tenant-demo',
    name: 'Inquilina Demo',
    email: 'inquilina@112233.es',
    password: '',
    passwordHash: '9f43cf3b2ee389bd63013060127a8243c50580f829de40f817aeba77b531eed6',
    role: 'tenant',
    phone: '+34 620 112 233',
    whatsapp: '+34 621 223 344',
    telegram: '@inquilina112233',
    about: 'Busco una habitación de larga estancia en Tenerife.',
    initials: 'ID',
    showPhone: false,
    showWhatsApp: false,
    allowContactForm: true,
    allowMessaging: true,
    blocked: false,
  },
  {
    id: 'host-demo',
    name: 'Anfitrión Demo',
    email: 'anfitrion@112233.es',
    password: '',
    passwordHash: '9f43cf3b2ee389bd63013060127a8243c50580f829de40f817aeba77b531eed6',
    role: 'host',
    phone: '+34 600 112 233',
    whatsapp: '+34 611 223 344',
    telegram: '@anfitrion112233',
    about: 'Publico habitaciones verificadas y respondo con rapidez.',
    initials: 'AD',
    showPhone: true,
    showWhatsApp: true,
    allowContactForm: true,
    allowMessaging: true,
    blocked: false,
  },
  {
    id: 'admin-demo',
    name: 'Administración 112233',
    email: 'admin@112233.es',
    password: '',
    passwordHash: 'aa5ff7ddeca7848ed7eb16270306d14ba2f7b65171ca0e700ec2e2adda115b83',
    role: 'admin',
    phone: '',
    whatsapp: '',
    telegram: '',
    about: 'Cuenta de administración para el entorno local de demostración.',
    initials: 'A1',
    showPhone: false,
    showWhatsApp: false,
    allowContactForm: false,
    allowMessaging: false,
    blocked: false,
  },
]

const isStringArray = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === 'string')

const isScopedStringArrays = (value: unknown): value is UserScopedState<string[]> =>
  Boolean(value) && typeof value === 'object' && Object.values(value as Record<string, unknown>).every(isStringArray)

const isSavedSearch = (value: unknown): value is SavedSearch =>
  Boolean(value) && typeof value === 'object' && typeof (value as SavedSearch).id === 'string' && typeof (value as SavedSearch).query === 'string'

const isScopedSavedSearches = (value: unknown): value is UserScopedState<SavedSearch[]> =>
  Boolean(value) && typeof value === 'object' && Object.values(value as Record<string, unknown>).every((items) => Array.isArray(items) && items.every(isSavedSearch))

const isLocalThread = (value: unknown): value is LocalMessageThread =>
  Boolean(value) && typeof value === 'object' && typeof (value as LocalMessageThread).listingId === 'string' && typeof (value as LocalMessageThread).messagePreview === 'string'

const isScopedLocalThreads = (value: unknown): value is UserScopedState<LocalMessageThread[]> =>
  Boolean(value) && typeof value === 'object' && Object.values(value as Record<string, unknown>).every((items) => Array.isArray(items) && items.every(isLocalThread))

const isLocalComment = (value: unknown): value is LocalListingComment =>
  Boolean(value) && typeof value === 'object' && typeof (value as LocalListingComment).id === 'string' && typeof (value as LocalListingComment).userId === 'string' && typeof (value as LocalListingComment).listingId === 'string' && typeof (value as LocalListingComment).text === 'string' && typeof (value as LocalListingComment).createdAt === 'string'

const isScopedLocalComments = (value: unknown): value is UserScopedState<LocalListingComment[]> =>
  Boolean(value) && typeof value === 'object' && Object.values(value as Record<string, unknown>).every((items) => Array.isArray(items) && items.every(isLocalComment))

const isListingArray = (value: unknown): value is Listing[] => Array.isArray(value) && value.every(isListingLike)

const isMockUser = (value: unknown): value is MockUser => {
  if (!value || typeof value !== 'object') return false
  const user = value as Partial<MockUser>
  return typeof user.id === 'string' && typeof user.name === 'string' && typeof user.email === 'string' && typeof user.password === 'string' && typeof user.passwordHash === 'string' && ['tenant', 'host', 'admin'].includes(user.role ?? '')
}

const isMockUserArray = (value: unknown): value is MockUser[] => Array.isArray(value) && value.every(isMockUser)

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

function readUsers() {
  return readJson<MockUser[]>(USERS_KEY, initialUsers, isMockUserArray).data
}

function readSession(users: DemoUser[]) {
  const parsed = parseJson<unknown>(localStorage.getItem(SESSION_KEY))
  return typeof parsed.data === 'string' && users.some((user) => user.id === parsed.data) ? parsed.data : null
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

async function hashPassword(value: string) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

const makeInitials = (name: string) => name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase() ?? '').join('') || 'US'

export function MockAppProvider({ children, context }: { children: ReactNode; context: Context<AppState | null> }) {
  const [listingLoad] = useState(readListings)
  const [initialUserLoad] = useState(readUsers)
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
  const [users, setUsers] = useState<MockUser[]>(initialUserLoad)
  const [currentUserId, setCurrentUserId] = useState<string | null>(() => readSession(initialUserLoad))
  const [storageError, setStorageError] = useState<string | null>(() => listingLoad.failure ? storageMessage(listingLoad.failure) : null)
  const orphanCleanupStarted = useRef(false)

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
    setFilters((current) => ({ ...current, minPrice: Math.min(current.minPrice, 350), maxPrice: Math.min(current.maxPrice, 350) }))
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
  useEffect(() => reportStorageFailure(persistJson(USERS_KEY, users)), [reportStorageFailure, users])
  useEffect(() => reportStorageFailure(persistJson(SESSION_KEY, currentUserId)), [currentUserId, reportStorageFailure])
  useEffect(() => {
    if (orphanCleanupStarted.current) return
    orphanCleanupStarted.current = true
    void cleanupOrphanedMedia(usedMediaReferences(allListings, users)).catch(() => undefined)
  }, [allListings, users])

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
    const location = resolveTenerifeLocation(nextQuery)
    if (!location || !isSupportedTenerifeQuery(nextQuery)) return sanitizeTenerifeHistory(current ?? [])
    return sanitizeTenerifeHistory([location.normalizedValue, ...(current ?? [])])
  }), [updateScope])

  const clearSearchHistory = useCallback(() => updateScope<string[]>(setHistoryScopes, () => []), [updateScope])

  const saveCurrentSearch = useCallback(() => updateScope(setSavedSearchScopes, (current) => {
    const searches = current ?? []
    const duplicate = searches.some((item) => item.query === query && item.rentalMode === rentalMode && JSON.stringify(item.filters) === JSON.stringify(filters) && JSON.stringify(item.polygon) === JSON.stringify(mapPolygon))
    if (duplicate) { toast.info('Esta búsqueda ya está guardada'); return searches }
    const saved = { id: `search-${Date.now()}`, query, rentalMode, filters: { ...filters }, alerts: true, createdAt: new Date().toISOString(), polygon: mapPolygon }
    toast.success('Búsqueda guardada. Te avisaremos de nuevos anuncios.')
    return [saved, ...searches]
  }), [filters, mapPolygon, query, rentalMode, updateScope])

  const restoreSavedSearch = useCallback((id: string) => {
    const found = savedSearches.find((item) => item.id === id)
    if (found) { setQuery(found.query); setRentalMode(found.rentalMode); setFilters(normalizeFilters(found.filters)); setMapPolygonState(found.polygon ?? []) }
    return found
  }, [savedSearches])

  const removeSavedSearch = useCallback((id: string) => updateScope(setSavedSearchScopes, (current) => (current ?? []).filter((item) => item.id !== id)), [updateScope])
  const toggleSearchAlerts = useCallback((id: string) => updateScope(setSavedSearchScopes, (current) => (current ?? []).map((item) => item.id === id ? { ...item, alerts: !item.alerts } : item)), [updateScope])
  const setMapPolygon = useCallback((points: MapPolygonPoint[]) => setMapPolygonState(points), [])
  const clearMapPolygon = useCallback(() => setMapPolygonState([]), [])

  const canManageListing = useCallback((listing: Listing) => Boolean(currentUser && (currentUser.role === 'admin' || (currentUser.role === 'host' && listing.ownerUserId === currentUser.id))), [currentUser])

  const createListing = useCallback(async (listing: Listing) => {
    if (!currentUser || currentUser.role === 'tenant') { toast.error('Necesitas una cuenta de anfitrión para publicar.'); return false }
    const stored = { ...listing, ownerUserId: currentUser.id, userCreated: true }
    setAllListings((current) => [stored, ...current])
    toast.success('Anuncio publicado y guardado en Mis anuncios')
    return true
  }, [currentUser])

  const updateListing = useCallback(async (id: string, listing: Listing) => {
    const previous = allListings.find((item) => item.id === id)
    if (!previous || !canManageListing(previous)) {
      if (previous) toast.error('No puedes gestionar un anuncio de otra cuenta.')
      return false
    }
    const next = { ...listing, id: previous.id, ownerUserId: previous.ownerUserId, userCreated: true }
    setAllListings((current) => current.map((item) => item.id === id ? next : item))
    return true
  }, [allListings, canManageListing])

  const mutateOwned = useCallback((id: string, mutate: (listing: Listing) => Listing | null) => setAllListings((current) => current.flatMap((listing) => {
    if (listing.id !== id) return [listing]
    if (!canManageListing(listing)) { toast.error('No puedes gestionar un anuncio de otra cuenta.'); return [listing] }
    const next = mutate(listing)
    return next ? [next] : []
  })), [canManageListing])

  const deleteListing = useCallback((id: string) => {
    const listing = allListings.find((item) => item.id === id)
    if (!listing) return
    if (!canManageListing(listing)) { toast.error('No puedes gestionar un anuncio de otra cuenta.'); return }
    const remaining = allListings.filter((item) => item.id !== id)
    const draftRecord = readDraftRecord()
    const deleteDraft = draftRecord?.value.listingId === id
    const draftMedia = deleteDraft ? collectMediaReferences(draftRecord?.value) : new Set<string>()
    if (deleteDraft) {
      localStorage.removeItem(DRAFT_KEY)
      localStorage.removeItem(LEGACY_DRAFT_KEY)
    }
    setAllListings(remaining)
    void removeUnusedMediaReferences([...listing.images, ...draftMedia], usedMediaReferences(remaining, users, deleteDraft ? null : draftRecord?.value)).catch((error) =>
      toast.error(error instanceof Error ? error.message : 'No se pudieron limpiar las imágenes locales.'),
    )
  }, [allListings, canManageListing, users])

  const setListingStatus = useCallback((id: string, status: ListingStatus) => {
    mutateOwned(id, (listing) => ({ ...listing, status, closedReason: status === 'Finalizado' ? listing.closedReason : undefined }))
  }, [mutateOwned])

  const renewListing = useCallback((id: string) => mutateOwned(id, (listing) => {
    const today = new Date(); today.setHours(0, 0, 0, 0)
    const currentExpiry = new Date(`${listing.expiresAt}T00:00:00`)
    const base = Number.isFinite(currentExpiry.getTime()) && currentExpiry > today ? currentExpiry : today
    base.setDate(base.getDate() + 30)
    return { ...listing, status: 'Publicado', expiresAt: base.toISOString().slice(0, 10), closedReason: undefined }
  }), [mutateOwned])

  const closeListing = useCallback((id: string) => mutateOwned(id, (listing) => ({ ...listing, status: 'Finalizado', closedReason: 'owner' })), [mutateOwned])
  const refreshListingLifecycle = useCallback(() => setAllListings((current) => current.map((listing) => expireListing(listing))), [])

  const addReport = useCallback((listingId: string, reason: string, comment: string) => {
    setReports((current) => [{ id: `REP-${Date.now().toString().slice(-6)}`, listingId, reason, comment, createdAt: new Date().toISOString(), status: 'Abierta' }, ...current])
  }, [])

  const addLocalMessage = useCallback(async (thread: Omit<LocalMessageThread, 'id' | 'createdAt' | 'status'> & { body?: string }) => {
    const stored: LocalMessageThread = { ...thread, id: `local-${Date.now()}`, createdAt: new Date().toISOString(), status: 'Demo local' }
    updateScope(setThreadScopes, (current) => [stored, ...(current ?? [])])
    return true
  }, [updateScope])

  const addLocalComment = useCallback((listingId: string, text: string) => updateScope(setCommentScopes, (current) => [{ id: `comment-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`, userId: scopeKey, listingId, text: text.trim(), createdAt: new Date().toISOString() }, ...(current ?? [])]), [scopeKey, updateScope])
  const updateLocalComment = useCallback((id: string, text: string) => updateScope(setCommentScopes, (current) => (current ?? []).map((comment) => comment.id === id ? { ...comment, text: text.trim(), updatedAt: new Date().toISOString() } : comment)), [updateScope])
  const deleteLocalComment = useCallback((id: string) => updateScope(setCommentScopes, (current) => (current ?? []).filter((comment) => comment.id !== id)), [updateScope])

  const login = useCallback(async (email: string, password: string) => {
    const normalizedEmail = email.trim().toLowerCase()
    const passwordHash = await hashPassword(password)
    const user = users.find((item) => item.email.toLowerCase() === normalizedEmail && item.passwordHash === passwordHash)
    if (!user) return 'Email o contraseña incorrectos.'
    if (user.blocked) return 'Esta cuenta está bloqueada.'
    setCurrentUserId(user.id)
    return null
  }, [users])

  const loginGoogle = useCallback(async () => 'Google no está configurado en el modo de demostración.', [])

  const register = useCallback(async (input: RegisterInput) => {
    const normalizedEmail = input.email.trim().toLowerCase()
    if (users.some((user) => user.email.toLowerCase() === normalizedEmail)) return 'Ya existe una cuenta con este email.'
    const passwordHash = await hashPassword(input.password)
    const user: MockUser = {
      id: `user-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      name: input.name.trim(),
      email: normalizedEmail,
      password: '',
      passwordHash,
      role: input.role,
      phone: '',
      whatsapp: '',
      telegram: '',
      about: '',
      initials: makeInitials(input.name),
      showPhone: false,
      showWhatsApp: false,
      allowContactForm: true,
      allowMessaging: true,
      blocked: false,
    }
    setUsers((current) => [...current, user])
    setCurrentUserId(user.id)
    return null
  }, [users])

  const logout = useCallback(() => setCurrentUserId(null), [])

  const updateProfile = useCallback((changes: ProfileUpdate) => {
    if (!currentUserId) return
    const previous = users.find((user) => user.id === currentUserId)
    const nextUsers = users.map((user) => user.id === currentUserId ? { ...user, ...changes, initials: changes.name ? makeInitials(changes.name) : user.initials } : user)
    setUsers(nextUsers)
    if (previous?.avatarRef && Object.prototype.hasOwnProperty.call(changes, 'avatarRef') && changes.avatarRef !== previous.avatarRef) {
      void removeUnusedMediaReferences([previous.avatarRef], usedMediaReferences(allListings, nextUsers)).catch((error) =>
        toast.error(error instanceof Error ? error.message : 'No se pudo limpiar el avatar anterior.'),
      )
    }
    toast.success('Perfil actualizado')
  }, [allListings, currentUserId, users])

  const deleteAccount = useCallback(async () => {
    if (!currentUserId) return false
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
    return true
  }, [allListings, currentUserId, users])

  const toggleUserBlocked = useCallback((id: string) => {
    if (currentUser?.role !== 'admin') return
    setUsers((current) => current.map((user) => user.id === id ? { ...user, blocked: !user.blocked } : user))
  }, [currentUser?.role])

  const activeFilterCount = useMemo(() => getActiveFilterKeys(filters).length, [filters])
  const value = useMemo<AppState>(() => ({
    rentalMode, setRentalMode, query, setQuery, favorites, toggleFavorite, discarded, discardListing, restoreDiscarded,
    filters, setFilters, resetFilters, activeFilterCount, searchHistory, addSearchHistory, clearSearchHistory,
    savedSearches, saveCurrentSearch, restoreSavedSearch, removeSavedSearch, toggleSearchAlerts,
    mapPolygon, setMapPolygon, clearMapPolygon, allListings, createListing, updateListing, deleteListing,
    setListingStatus, renewListing, closeListing, refreshListingLifecycle, canManageListing, reports, addReport,
    localThreads, addLocalMessage, localComments, addLocalComment, updateLocalComment, deleteLocalComment,
    users, currentUser, login, loginGoogle, register, logout, updateProfile, deleteAccount, toggleUserBlocked,
    storageError, clearStorageError: () => setStorageError(null),
  }), [
    rentalMode, query, favorites, toggleFavorite, discarded, discardListing, restoreDiscarded, filters, resetFilters,
    activeFilterCount, searchHistory, addSearchHistory, clearSearchHistory, savedSearches, saveCurrentSearch,
    restoreSavedSearch, removeSavedSearch, toggleSearchAlerts, mapPolygon, setMapPolygon, clearMapPolygon, allListings,
    createListing, updateListing, deleteListing, setListingStatus, renewListing, closeListing, refreshListingLifecycle,
    canManageListing, reports, addReport, localThreads, addLocalMessage, localComments, addLocalComment,
    updateLocalComment, deleteLocalComment, users, currentUser, login, loginGoogle, register, logout, updateProfile,
    deleteAccount, toggleUserBlocked, storageError,
  ])

  const Provider = context.Provider
  return <Provider value={value}>{children}</Provider>
}
