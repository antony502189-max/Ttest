import { api, resolveApiUrl } from '@/api/client'
import type { Filters, Listing, ListingStatus, TenantRequirement } from '@/types'

type ListingDto = {
  id: string
  ownerUserId: string
  owner: { name: string; initials: string; since: string | null; response: string; verified: boolean }
  contactPhone: string | null
  contactWhatsapp: string | null
  contactEmail: string | null
  showPhone: boolean
  showWhatsApp: boolean
  allowContactForm: boolean
  coverImageUrl: string | null
  imageUrls: string[]
  title: string
  city: string
  area: string
  approximateAddress: string
  street?: string
  postcode?: string
  exactLatitude?: number | null
  exactLongitude?: number | null
  price: number | null
  cadence: 'mes' | 'noche'
  monthlyPrice: number | null
  nightlyPrice: number | null
  weeklyPrice: number | null
  rentalMode: 'long' | 'holiday'
  roomType: Listing['roomType']
  availableFrom: string | null
  availableUntil: string | null
  minimumStayMonths: number | null
  minimumNights: number | null
  depositAmount: number | null
  depositText: string | null
  billsIncluded: boolean | null
  billsText: string | null
  bathroom: Listing['bathroom'] | null
  kitchen: Listing['kitchen'] | null
  furnished: boolean | null
  roomSizeM2: number | null
  bedroomCount: number | null
  currentResidents: number
  roomCapacity: 1 | 2 | null
  shower: Listing['shower']
  tenantRequirement: TenantRequirement | null
  smokingAllowed: boolean | null
  petsAllowed: boolean | null
  childrenAllowed: boolean | null
  empadronamientoAllowed: boolean | null
  restrictions: string[]
  amenities: string[]
  status: string
  latitude: number
  longitude: number
  description: string
  homeDescription: string
  advertiserName: string | null
  advertiserType: Listing['advertiserType'] | null
  source: string | null
  isExternal: boolean
  primarySource: string | null
  sourceUrl: string | null
  sourcePriceText: string | null
  priceCurrency: string | null
  pricePeriod: 'month' | 'night' | 'week' | null
  priceIsFrom: boolean | null
  publishedAt: string | null
  expiresAt: string | null
  views: number
  closedReason: Listing['closedReason'] | null
}

type ListingSearchDto = { items: ListingDto[]; total: number; limit: number; offset: number }
type DraftPrivateFields = {
  street?: string
  postcode?: string
  contactName?: string
  contactPhone?: string
  contactWhatsapp?: string
}

const statusMap: Record<string, ListingStatus> = {
  draft: 'Borrador', pending: 'Pendiente', published: 'Publicado', hidden: 'Oculto', closed: 'Finalizado', rejected: 'Rechazado',
}

const remoteStatusMap: Record<ListingStatus, string> = {
  Borrador: 'draft', Pendiente: 'pending', Publicado: 'published', Oculto: 'hidden', Finalizado: 'closed', Rechazado: 'rejected',
}

function dateOnly(value: string | null, fallback: string) {
  return value ? value.slice(0, 10) : fallback
}

export function toListing(dto: ListingDto): Listing {
  const availableFrom = dateOnly(dto.availableFrom, new Date().toISOString().slice(0, 10))
  const price = dto.price ?? (dto.rentalMode === 'holiday' ? dto.nightlyPrice : dto.monthlyPrice) ?? 0
  return {
    id: dto.id,
    title: dto.title,
    city: dto.city,
    area: dto.area,
    approximateAddress: dto.approximateAddress,
    ...(dto.street !== undefined ? { street: dto.street } : {}),
    ...(dto.postcode !== undefined ? { postcode: dto.postcode } : {}),
    ...(dto.exactLatitude != null && dto.exactLongitude != null
      ? { exactCoordinates: { lat: dto.exactLatitude, lng: dto.exactLongitude } }
      : {}),
    price,
    cadence: dto.cadence,
    monthlyPrice: dto.monthlyPrice ?? undefined,
    nightlyPrice: dto.nightlyPrice ?? undefined,
    weeklyPrice: dto.weeklyPrice ?? undefined,
    rentalMode: dto.rentalMode,
    roomType: dto.roomType,
    available: dto.availableFrom ? `Disponible desde ${availableFrom}` : 'Consultar disponibilidad',
    availableFrom,
    availableUntil: dto.availableUntil ? dateOnly(dto.availableUntil, availableFrom) : undefined,
    minimumStay: dto.rentalMode === 'holiday'
      ? dto.minimumNights == null ? 'Consultar estancia mínima' : `Mínimo ${dto.minimumNights} noche(s)`
      : dto.minimumStayMonths == null ? 'Consultar estancia mínima' : `Mínimo ${dto.minimumStayMonths} mes(es)`,
    minimumStayMonths: dto.minimumStayMonths,
    minimumNights: dto.minimumNights ?? undefined,
    deposit: dto.depositText ?? (dto.depositAmount != null ? `${dto.depositAmount} € de fianza` : 'Consultar fianza'),
    depositAmount: dto.depositAmount,
    bills: dto.billsText ?? (dto.billsIncluded == null ? 'Consultar gastos' : dto.billsIncluded ? 'Gastos incluidos' : 'Gastos no incluidos'),
    billsIncluded: dto.billsIncluded,
    bathroom: dto.bathroom,
    kitchen: dto.kitchen,
    furnished: dto.furnished,
    roomSizeM2: dto.roomSizeM2,
    bedroomCount: dto.bedroomCount ?? undefined,
    currentResidents: dto.currentResidents,
    roomCapacity: dto.roomCapacity,
    shower: dto.shower,
    coordinates: { lat: dto.latitude, lng: dto.longitude },
    tenantRequirement: dto.tenantRequirement,
    smokingAllowed: dto.smokingAllowed,
    petsAllowed: dto.petsAllowed,
    childrenAllowed: dto.childrenAllowed,
    empadronamientoAllowed: dto.empadronamientoAllowed,
    restrictions: dto.restrictions,
    amenities: dto.amenities,
    description: dto.description,
    homeDescription: dto.homeDescription,
    images: dto.imageUrls.map(resolveApiUrl),
    owner: {
      name: dto.owner.name,
      initials: dto.owner.initials,
      since: dto.owner.since ? new Date(dto.owner.since).getFullYear().toString() : 'Cuenta verificada',
      response: dto.owner.response,
      verified: dto.owner.verified,
    },
    advertiserType: dto.advertiserType ?? 'Particular',
    source: dto.source ?? undefined,
    isExternal: dto.isExternal,
    primarySource: dto.primarySource ?? undefined,
    sourceUrl: dto.sourceUrl ?? undefined,
    sourcePriceText: dto.sourcePriceText ?? undefined,
    priceCurrency: dto.priceCurrency ?? undefined,
    pricePeriod: dto.pricePeriod ?? undefined,
    priceIsFrom: dto.priceIsFrom ?? undefined,
    status: statusMap[dto.status] ?? 'Publicado',
    publishedAt: dateOnly(dto.publishedAt, availableFrom),
    views: dto.views,
    expiresAt: dateOnly(dto.expiresAt, '2099-12-31'),
    ownerUserId: dto.ownerUserId,
    contactPhone: dto.contactPhone ?? undefined,
    contactWhatsapp: dto.contactWhatsapp ?? undefined,
    contactEmail: dto.contactEmail ?? undefined,
    showPhone: dto.showPhone,
    showWhatsApp: dto.showWhatsApp,
    allowContactForm: dto.allowContactForm,
    closedReason: dto.closedReason ?? undefined,
  }
}

async function fetchAllSearch(body: Record<string, unknown>, signal?: AbortSignal) {
  const pageSize = 100
  const items: ListingDto[] = []
  let offset = 0
  let total = 0
  do {
    const response = await api<ListingSearchDto>('/listings/search', {
      method: 'POST', body: JSON.stringify({ ...body, limit: pageSize, offset }), signal,
    })
    items.push(...response.items)
    total = response.total
    if (!response.items.length) break
    offset += response.items.length
  } while (items.length < total)
  return items.map(toListing)
}

export function getPublicListings(signal?: AbortSignal) {
  return fetchAllSearch({ sort: 'newest' }, signal)
}

export function getCatalogVersion(signal?: AbortSignal) {
  return api<{ version: string; updatedAt: string }>('/listings/catalog-version', { signal })
}

export async function getOwnedListings() {
  return (await api<ListingDto[]>('/listings/mine')).map(toListing)
}

export async function getPublicListing(id: string) {
  return toListing(await api<ListingDto>(`/listings/${id}`))
}

export type RoomCountFilter = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | '10+'

export type ListingSearchInput = {
  rentalMode: Listing['rentalMode']
  minPrice: number
  maxPrice: number
  filters: Filters
  query?: string
  roomTypes?: Listing['roomType'][]
  bedroomCounts?: RoomCountFilter[]
  bounds?: { north: number; south: number; east: number; west: number }
  polygon?: Array<{ latitude: number; longitude: number }>
  center?: { latitude: number; longitude: number }
  radiusKm?: number
  sort?: 'newest' | 'oldest' | 'price_asc' | 'price_desc'
}

function routeSearchState() {
  const hashQuery = window.location.hash.split('?', 2)[1] ?? ''
  const params = new URLSearchParams(hashQuery)
  const roomTypes = (params.get('tiposHabitacion') ?? '')
    .split('|')
    .filter((value): value is Listing['roomType'] => ['Habitación individual', 'Habitación compartida', 'Estudio'].includes(value))
  const bedroomCounts = (params.get('habitaciones') ?? '')
    .split('|')
    .map((value): RoomCountFilter | null => {
      if (value === '10+') return value
      const number = Number(value)
      return Number.isInteger(number) && number >= 1 && number <= 10 ? number as RoomCountFilter : null
    })
    .filter((value): value is RoomCountFilter => value !== null)
  const latitude = Number(params.get('lat'))
  const longitude = Number(params.get('lng'))
  const nearby = params.get('cerca') === '1' && Number.isFinite(latitude) && Number.isFinite(longitude)
  return {
    query: params.get('q')?.trim() || 'Tenerife',
    roomTypes,
    bedroomCounts,
    center: nearby ? { latitude, longitude } : undefined,
    radiusKm: nearby ? Math.min(50, Math.max(1, Number(params.get('radio')) || 15)) : undefined,
  }
}

export function searchPublicListings(input: ListingSearchInput) {
  const route = routeSearchState()
  const { bounds, polygon, filters, ...payload } = input
  const yesNo = (value: string) => value === 'Cualquiera' ? undefined : value === 'Sí'
  const publicationDays = filters.publicationDate === '24h' ? 1 : filters.publicationDate === '7d' ? 7 : filters.publicationDate === '30d' ? 30 : undefined
  const body = {
    ...payload,
    query: input.query ?? route.query,
    roomTypes: input.roomTypes ?? route.roomTypes,
    bedroomCounts: input.bedroomCounts ?? route.bedroomCounts,
    center: input.center ?? route.center,
    radiusKm: input.radiusKm ?? route.radiusKm,
    ...(filters.roomType !== 'Cualquiera' ? { roomType: filters.roomType } : {}),
    ...(filters.available ? { availableFrom: filters.available } : {}),
    ...(filters.minStay !== 'Cualquiera' ? { maxMinimumStayMonths: Number(filters.minStay) } : {}),
    ...(filters.conditions.length ? { restrictions: filters.conditions } : {}),
    ...(filters.tenantRequirement !== 'Cualquiera' ? { tenantRequirement: filters.tenantRequirement } : {}),
    ...(filters.bathroom !== 'Cualquiera' ? { bathroom: filters.bathroom } : {}),
    ...(filters.kitchen !== 'Cualquiera' ? { kitchen: filters.kitchen } : {}),
    ...(filters.furnished ? { furnished: true } : {}),
    ...(filters.billsIncluded ? { billsIncluded: true } : {}),
    ...(filters.deposit !== 'Cualquiera' ? { deposit: filters.deposit } : {}),
    minRoomSizeM2: filters.roomSizeMin,
    maxRoomSizeM2: filters.roomSizeMax,
    ...(filters.shower !== 'Cualquiera' ? { shower: filters.shower } : {}),
    ...(filters.currentResidents === '5+' ? { minCurrentResidents: 5 } : filters.currentResidents !== 'Cualquiera' ? { currentResidents: Number(filters.currentResidents) } : {}),
    ...(filters.roomCapacity !== 'Cualquiera' ? { roomCapacity: Number(filters.roomCapacity) } : {}),
    ...(input.rentalMode === 'holiday' && filters.minimumNights > 0 ? { maxMinimumNights: filters.minimumNights } : {}),
    ...(input.rentalMode === 'holiday' && filters.availableUntil ? { availableUntil: filters.availableUntil } : {}),
    ...(yesNo(filters.smoking) !== undefined ? { smokingAllowed: yesNo(filters.smoking) } : {}),
    ...(yesNo(filters.pets) !== undefined ? { petsAllowed: yesNo(filters.pets) } : {}),
    ...(yesNo(filters.children) !== undefined ? { childrenAllowed: yesNo(filters.children) } : {}),
    ...(yesNo(filters.empadronamiento) !== undefined ? { empadronamientoAllowed: yesNo(filters.empadronamiento) } : {}),
    ...(publicationDays ? { publishedWithinDays: publicationDays } : {}),
    ...(filters.advertiserType !== 'Cualquiera' ? { advertiserType: filters.advertiserType } : {}),
    ...(filters.amenities.length ? { amenities: filters.amenities } : {}),
    ...(bounds ? {
      minLatitude: bounds.south, maxLatitude: bounds.north,
      minLongitude: bounds.west, maxLongitude: bounds.east,
    } : {}),
    ...(polygon?.length ? { polygon } : {}),
  }
  return fetchAllSearch(body)
}

function readDraftPrivateFields(listingId?: string): DraftPrivateFields | null {
  for (const key of ['112233:listing-draft:v3', '112233:listing-draft:v2']) {
    try {
      const raw = localStorage.getItem(key)
      if (!raw) continue
      const parsed = JSON.parse(raw) as { listingId?: string; data?: DraftPrivateFields } | DraftPrivateFields
      const recordListingId = 'listingId' in parsed ? parsed.listingId : undefined
      if (recordListingId && listingId && recordListingId !== listingId) continue
      const data = 'data' in parsed && parsed.data ? parsed.data : parsed as DraftPrivateFields
      return data
    } catch { /* Ignore corrupted legacy drafts. */ }
  }
  return null
}

async function syncContactProfile(listing: Listing) {
  const draft = readDraftPrivateFields(listing.id)
  const name = (draft?.contactName || listing.owner.name).trim()
  await api('/users/me', {
    method: 'PATCH',
    body: JSON.stringify({
      name,
      phone: draft?.contactPhone ?? listing.contactPhone ?? '',
      whatsapp: draft?.contactWhatsapp ?? listing.contactWhatsapp ?? '',
      showPhone: listing.showPhone,
      showWhatsApp: listing.showWhatsApp,
      allowContactForm: listing.allowContactForm,
    }),
  })
}

function listingPayload(listing: Listing, existing?: Listing) {
  const draft = readDraftPrivateFields(listing.id)
  const exact = listing.exactCoordinates ?? existing?.exactCoordinates
  return {
    title: listing.title, city: listing.city, area: listing.area,
    street: draft?.street?.trim() || listing.street || existing?.street || '',
    postcode: draft?.postcode?.trim() || listing.postcode || existing?.postcode || '',
    approximateAddress: listing.approximateAddress,
    rentalMode: listing.rentalMode, monthlyPrice: listing.monthlyPrice ?? null, nightlyPrice: listing.nightlyPrice ?? null,
    weeklyPrice: listing.weeklyPrice ?? null, roomType: listing.roomType, availableFrom: listing.availableFrom,
    availableUntil: listing.availableUntil ?? null, minimumStayMonths: listing.minimumStayMonths,
    minimumNights: listing.minimumNights ?? null, depositAmount: listing.depositAmount, billsIncluded: listing.billsIncluded,
    bathroom: listing.bathroom, kitchen: listing.kitchen, furnished: listing.furnished, roomSizeM2: listing.roomSizeM2,
    bedroomCount: listing.bedroomCount ?? null, currentResidents: listing.currentResidents, roomCapacity: listing.roomCapacity,
    shower: listing.shower, tenantRequirement: listing.tenantRequirement, smokingAllowed: listing.smokingAllowed,
    petsAllowed: listing.petsAllowed, childrenAllowed: listing.childrenAllowed, empadronamientoAllowed: listing.empadronamientoAllowed,
    restrictions: listing.restrictions, amenities: listing.amenities, latitude: listing.coordinates.lat,
    longitude: listing.coordinates.lng, exactLatitude: exact?.lat ?? null, exactLongitude: exact?.lng ?? null,
    description: listing.description, homeDescription: listing.homeDescription,
    advertiserType: listing.advertiserType, source: listing.source ?? null,
    expiresAt: listing.expiresAt ? `${listing.expiresAt}T00:00:00Z` : null,
  }
}

export async function createRemoteListing(listing: Listing) {
  await syncContactProfile(listing)
  return toListing(await api<ListingDto>('/listings', { method: 'POST', body: JSON.stringify(listingPayload(listing)) }))
}

export async function updateRemoteListing(id: string, listing: Listing) {
  await syncContactProfile(listing)
  const existing = (await getOwnedListings()).find((item) => item.id === id)
  return toListing(await api<ListingDto>(`/listings/${id}`, {
    method: 'PATCH', body: JSON.stringify(listingPayload(listing, existing)),
  }))
}

export async function setRemoteListingStatus(id: string, status: ListingStatus) {
  return toListing(await api<ListingDto>(`/listings/${id}`, {
    method: 'PATCH', body: JSON.stringify({ status: remoteStatusMap[status] }),
  }))
}

export async function renewRemoteListing(id: string) {
  return toListing(await api<ListingDto>(`/listings/${id}/renew`, { method: 'POST' }))
}

export const deleteRemoteListing = (id: string) => api<void>(`/listings/${id}`, { method: 'DELETE' })
