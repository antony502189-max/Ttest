import { api, resolveApiUrl } from '@/api/client'
import { defaultFilters } from '@/data/listings'
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
  roomCapacity: number | null
  shower: Listing['shower']
  homeSizeM2: number | null
  bathroomCount: number | null
  rentalUnit: Listing['rentalUnit'] | null
  bedType: Listing['bedType'] | null
  bedCount: number | null
  currentRoomResidents: number | null
  availableSpots: number | null
  toilet: Listing['toilet'] | null
  householdGender: Listing['householdGender'] | null
  householdHasChildren: boolean | null
  heatingType: Listing['heatingType'] | null
  accessible: boolean | null
  floor: Listing['floor'] | null
  couplesAllowed: boolean | null
  acceptedTenantTypes: NonNullable<Listing['acceptedTenantTypes']>
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
  promoted: boolean
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
    homeSizeM2: dto.homeSizeM2,
    bathroomCount: dto.bathroomCount,
    rentalUnit: dto.rentalUnit,
    bedType: dto.bedType,
    bedCount: dto.bedCount,
    currentRoomResidents: dto.currentRoomResidents,
    availableSpots: dto.availableSpots,
    toilet: dto.toilet,
    householdGender: dto.householdGender,
    householdHasChildren: dto.householdHasChildren,
    heatingType: dto.heatingType,
    accessible: dto.accessible,
    floor: dto.floor,
    couplesAllowed: dto.couplesAllowed,
    acceptedTenantTypes: dto.acceptedTenantTypes,
    coordinates: { lat: dto.latitude, lng: dto.longitude },
    tenantRequirement: dto.tenantRequirement,
    smokingAllowed: dto.smokingAllowed,
    petsAllowed: dto.petsAllowed,
    childrenAllowed: dto.childrenAllowed,
    empadronamientoAllowed: dto.empadronamientoAllowed,
    restrictions: dto.restrictions,
    amenities: dto.amenities.map((item) => item === 'Fibra' ? 'Wi-Fi' : item),
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
    closedReason: dto.closedReason ?? undefined,
    promoted: dto.promoted,
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

export type ListingSearchInput = {
  rentalMode: Listing['rentalMode']
  minPrice: number
  maxPrice: number
  filters: Filters
  query?: string
  roomTypes?: Listing['roomType'][]
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
  const latitude = Number(params.get('lat'))
  const longitude = Number(params.get('lng'))
  const nearby = params.get('cerca') === '1' && Number.isFinite(latitude) && Number.isFinite(longitude)
  return {
    query: params.get('q')?.trim() || 'Tenerife',
    roomTypes,
    center: nearby ? { latitude, longitude } : undefined,
    radiusKm: nearby ? Math.min(50, Math.max(1, Number(params.get('radio')) || 15)) : undefined,
  }
}

export function searchPublicListings(input: ListingSearchInput) {
  const route = routeSearchState()
  const { bounds, polygon, filters, minPrice, maxPrice, ...payload } = input
  const yesNo = (value: string) => value === 'Cualquiera' ? undefined : value === 'Sí'
  const publicationDays = filters.publicationDate === '24h' ? 1 : filters.publicationDate === '7d' ? 7 : filters.publicationDate === '30d' ? 30 : undefined
  const body = {
    ...payload,
    ...(minPrice !== defaultFilters.minPrice ? { minPrice } : {}),
    ...(maxPrice !== defaultFilters.maxPrice ? { maxPrice } : {}),
    query: input.query ?? route.query,
    roomTypes: input.roomTypes ?? route.roomTypes,
    center: input.center ?? route.center,
    radiusKm: input.radiusKm ?? route.radiusKm,
    ...(filters.roomType !== 'Cualquiera' ? { roomType: filters.roomType } : {}),
    ...(filters.available ? { availableFrom: filters.available } : {}),
    ...(filters.availableUntil ? { availableUntil: filters.availableUntil } : {}),
    ...(filters.minStay !== 'Cualquiera' ? { maxMinimumStayMonths: Number(filters.minStay) } : {}),
    ...(filters.conditions.length ? { restrictions: filters.conditions } : {}),
    ...(filters.tenantRequirement !== 'Cualquiera' && filters.tenantRequirement !== 'any'
      ? { tenantRequirement: filters.tenantRequirement }
      : {}),
    ...(filters.bathroom !== 'Cualquiera' ? { bathroom: filters.bathroom } : {}),
    ...(filters.kitchen !== 'Cualquiera' ? { kitchen: filters.kitchen } : {}),
    ...(filters.furnished ? { furnished: true } : {}),
    ...(filters.billsIncluded ? { billsIncluded: true } : {}),
    ...(filters.deposit !== 'Cualquiera' ? { deposit: filters.deposit } : {}),
    ...(filters.roomSizeMin !== defaultFilters.roomSizeMin ? { minRoomSizeM2: filters.roomSizeMin } : {}),
    ...(filters.roomSizeMax !== defaultFilters.roomSizeMax ? { maxRoomSizeM2: filters.roomSizeMax } : {}),
    ...(filters.homeSizeMin !== defaultFilters.homeSizeMin ? { minHomeSizeM2: filters.homeSizeMin } : {}),
    ...(filters.homeSizeMax !== defaultFilters.homeSizeMax ? { maxHomeSizeM2: filters.homeSizeMax } : {}),
    ...(filters.bathroomCountMin > 0 ? { minBathroomCount: filters.bathroomCountMin } : {}),
    ...(filters.rentalUnit !== 'Cualquiera' ? { rentalUnit: filters.rentalUnit } : {}),
    ...(filters.bedType !== 'Cualquiera' ? { bedType: filters.bedType } : {}),
    ...(filters.bedCountMin > 0 ? { minBedCount: filters.bedCountMin } : {}),
    ...(filters.shower !== 'Cualquiera' ? { shower: filters.shower } : {}),
    ...(filters.toilet !== 'Cualquiera' ? { toilet: filters.toilet } : {}),
    ...(filters.currentResidents === '5+' ? { minCurrentResidents: 5 } : filters.currentResidents !== 'Cualquiera' ? { currentResidents: Number(filters.currentResidents) } : {}),
    ...(filters.roomResidents !== 'Cualquiera' ? { currentRoomResidents: Number(filters.roomResidents) } : {}),
    ...(filters.roomCapacity !== 'Cualquiera' ? { roomCapacity: Number(filters.roomCapacity) } : {}),
    ...(filters.availableSpotsMin > 0 ? { minAvailableSpots: filters.availableSpotsMin } : {}),
    ...(input.rentalMode === 'holiday' && filters.minimumNights > 0 ? { maxMinimumNights: filters.minimumNights } : {}),
    ...(yesNo(filters.smoking) !== undefined ? { smokingAllowed: yesNo(filters.smoking) } : {}),
    ...(yesNo(filters.pets) !== undefined ? { petsAllowed: yesNo(filters.pets) } : {}),
    ...(yesNo(filters.children) !== undefined ? { childrenAllowed: yesNo(filters.children) } : {}),
    ...(yesNo(filters.couplesAllowed) !== undefined ? { couplesAllowed: yesNo(filters.couplesAllowed) } : {}),
    ...(filters.householdGender !== 'Cualquiera' ? { householdGender: filters.householdGender } : {}),
    ...(yesNo(filters.householdHasChildren) !== undefined ? { householdHasChildren: yesNo(filters.householdHasChildren) } : {}),
    ...(filters.heatingType !== 'Cualquiera' ? { heatingType: filters.heatingType } : {}),
    ...(yesNo(filters.accessible) !== undefined ? { accessible: yesNo(filters.accessible) } : {}),
    ...(filters.floor !== 'Cualquiera' ? { floor: filters.floor } : {}),
    ...(filters.acceptedTenantTypes.length ? { acceptedTenantTypes: filters.acceptedTenantTypes } : {}),
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
    billsText: listing.bills,
    bathroom: listing.bathroom, kitchen: listing.kitchen, furnished: listing.furnished, roomSizeM2: listing.roomSizeM2,
    bedroomCount: listing.bedroomCount ?? null, currentResidents: listing.currentResidents, roomCapacity: listing.roomCapacity,
    shower: listing.shower, homeSizeM2: listing.homeSizeM2 ?? null, bathroomCount: listing.bathroomCount ?? null,
    rentalUnit: listing.rentalUnit ?? null, bedType: listing.bedType ?? null, bedCount: listing.bedCount ?? null,
    currentRoomResidents: listing.currentRoomResidents ?? null, toilet: listing.toilet ?? null,
    householdGender: listing.householdGender ?? null, householdHasChildren: listing.householdHasChildren ?? null,
    heatingType: listing.heatingType ?? null, accessible: listing.accessible ?? null, floor: listing.floor ?? null, couplesAllowed: listing.couplesAllowed ?? null,
    acceptedTenantTypes: listing.acceptedTenantTypes ?? [],
    tenantRequirement: listing.tenantRequirement, smokingAllowed: listing.smokingAllowed,
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
