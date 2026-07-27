import { api, resolveApiUrl } from '@/api/client'
import type { Listing, ListingStatus, TenantRequirement } from '@/types'

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
  price: number | null
  cadence: 'mes' | 'noche'
  monthlyPrice: number | null
  nightlyPrice: number | null
  weeklyPrice: number | null
  rentalMode: 'long' | 'holiday'
  roomType: Listing['roomType']
  availableFrom: string | null
  availableUntil: string | null
  minimumStayMonths: number
  minimumNights: number | null
  depositAmount: number
  billsIncluded: boolean
  bathroom: Listing['bathroom']
  kitchen: Listing['kitchen']
  furnished: boolean
  roomSizeM2: number
  bedroomCount: number | null
  currentResidents: number
  roomCapacity: 1 | 2
  shower: Listing['shower']
  tenantRequirement: TenantRequirement
  smokingAllowed: boolean
  petsAllowed: boolean
  childrenAllowed: boolean
  empadronamientoAllowed: boolean
  restrictions: string[]
  amenities: string[]
  status: string
  latitude: number
  longitude: number
  description: string
  homeDescription: string
  advertiserType: Listing['advertiserType']
  source: string | null
  publishedAt: string | null
  expiresAt: string | null
  views: number
  closedReason: Listing['closedReason']
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
    minimumStay: dto.rentalMode === 'holiday' ? `Mínimo ${dto.minimumNights ?? 1} noche(s)` : `Mínimo ${dto.minimumStayMonths} mes(es)`,
    minimumStayMonths: dto.minimumStayMonths,
    minimumNights: dto.minimumNights ?? undefined,
    deposit: dto.depositAmount ? `${dto.depositAmount} € de fianza` : 'Sin fianza',
    depositAmount: dto.depositAmount,
    bills: dto.billsIncluded ? 'Gastos incluidos' : 'Gastos no incluidos',
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
    advertiserType: dto.advertiserType,
    source: dto.source ?? undefined,
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

export async function getPublicListings() {
  return (await api<ListingDto[]>('/listings')).map(toListing)
}

export async function getPublicListing(id: string) {
  return toListing(await api<ListingDto>(`/listings/${id}`))
}

export type ListingSearchInput = {
  rentalMode: Listing['rentalMode']
  minPrice: number
  maxPrice: number
  bounds?: { north: number; south: number; east: number; west: number }
  polygon?: Array<{ latitude: number; longitude: number }>
  sort?: 'newest' | 'price_asc' | 'price_desc'
}

export async function searchPublicListings(input: ListingSearchInput) {
  const { bounds, polygon, ...payload } = input
  const body = {
    ...payload,
    limit: 100,
    ...(bounds ? {
      minLatitude: bounds.south, maxLatitude: bounds.north,
      minLongitude: bounds.west, maxLongitude: bounds.east,
    } : {}),
    ...(polygon?.length ? { polygon } : {}),
  }
  const response = await api<{ items: ListingDto[] }>('/listings/search', {
    method: 'POST', body: JSON.stringify(body),
  })
  return response.items.map(toListing)
}

function listingPayload(listing: Listing) {
  return {
    title: listing.title, city: listing.city, area: listing.area, approximateAddress: listing.approximateAddress,
    rentalMode: listing.rentalMode, monthlyPrice: listing.monthlyPrice ?? null, nightlyPrice: listing.nightlyPrice ?? null,
    weeklyPrice: listing.weeklyPrice ?? null, roomType: listing.roomType, availableFrom: listing.availableFrom,
    availableUntil: listing.availableUntil ?? null, minimumStayMonths: listing.minimumStayMonths,
    minimumNights: listing.minimumNights ?? null, depositAmount: listing.depositAmount, billsIncluded: listing.billsIncluded,
    bathroom: listing.bathroom, kitchen: listing.kitchen, furnished: listing.furnished, roomSizeM2: listing.roomSizeM2,
    bedroomCount: listing.bedroomCount ?? null, currentResidents: listing.currentResidents, roomCapacity: listing.roomCapacity,
    shower: listing.shower, tenantRequirement: listing.tenantRequirement, smokingAllowed: listing.smokingAllowed,
    petsAllowed: listing.petsAllowed, childrenAllowed: listing.childrenAllowed, empadronamientoAllowed: listing.empadronamientoAllowed,
    restrictions: listing.restrictions, amenities: listing.amenities, latitude: listing.coordinates.lat,
    longitude: listing.coordinates.lng, description: listing.description, homeDescription: listing.homeDescription,
    advertiserType: listing.advertiserType, source: listing.source ?? null,
    expiresAt: listing.expiresAt ? `${listing.expiresAt}T00:00:00Z` : null,
  }
}

export async function createRemoteListing(listing: Listing) {
  return toListing(await api<ListingDto>('/listings', { method: 'POST', body: JSON.stringify(listingPayload(listing)) }))
}

export async function updateRemoteListing(id: string, listing: Listing) {
  return toListing(await api<ListingDto>(`/listings/${id}`, { method: 'PATCH', body: JSON.stringify(listingPayload(listing)) }))
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
