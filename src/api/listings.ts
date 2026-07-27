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
