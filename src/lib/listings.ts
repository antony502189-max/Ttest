import type { Listing, TenantRequirement } from '@/types'
import { TENERIFE_CENTER } from '@/lib/tenerife'

export const tenantRequirementLabels: Record<TenantRequirement, string> = {
  'single-man': 'Solo un hombre',
  'single-woman': 'Solo una mujer',
  'single-person': 'Una persona',
  couple: 'Solo pareja',
  any: 'Sin restricción',
}

export function getPrimaryPrice(listing: Listing) {
  return listing.rentalMode === 'holiday'
    ? listing.nightlyPrice ?? listing.price
    : listing.monthlyPrice ?? listing.price
}

export function getPrimaryCadence(listing: Listing): 'mes' | 'noche' {
  return listing.rentalMode === 'holiday' ? 'noche' : 'mes'
}

export function getCriticalRestrictions(listing: Listing): string[] {
  const restrictions = [
    tenantRequirementLabels[listing.tenantRequirement],
    `Habitación para ${listing.roomCapacity} ${listing.roomCapacity === 1 ? 'persona' : 'personas'}`,
    listing.petsAllowed ? 'Mascotas permitidas' : 'Sin mascotas',
    listing.smokingAllowed ? 'Se puede fumar' : 'No fumar',
    listing.childrenAllowed ? 'Niños permitidos' : 'Sin niños',
    listing.empadronamientoAllowed ? 'Empadronamiento posible' : 'Sin empadronamiento',
    listing.rentalMode === 'holiday'
      ? `Estancia mínima de ${listing.minimumNights ?? 1} ${(listing.minimumNights ?? 1) === 1 ? 'noche' : 'noches'}`
      : `Estancia mínima de ${listing.minimumStayMonths} ${listing.minimumStayMonths === 1 ? 'mes' : 'meses'}`,
    listing.billsIncluded ? 'Gastos incluidos' : listing.bills,
  ]
  return [...new Set(restrictions.filter(Boolean))]
}

export function buildContactConfirmationText(listing: Listing) {
  const conditions = getCriticalRestrictions(listing)
    .slice(0, 5)
    .map((item) => item.charAt(0).toLocaleLowerCase('es-ES') + item.slice(1))
  const last = conditions.pop()
  return `Confirmo que cumplo estas condiciones: ${conditions.join(', ')}${conditions.length && last ? ' y ' : ''}${last ?? ''}.`
}

type LegacyListing = Partial<Listing> & {
  size?: number
  occupants?: number
  genderPreference?: string
  couplesAllowed?: boolean
}

function inferTenantRequirement(listing: LegacyListing): TenantRequirement {
  if (listing.tenantRequirement) return listing.tenantRequirement
  if (listing.genderPreference === 'Solo hombre') return 'single-man'
  if (listing.genderPreference === 'Solo mujer') return 'single-woman'
  if (listing.couplesAllowed && listing.roomType !== 'Habitación individual') return 'couple'
  return 'any'
}

export function isListingLike(value: unknown): value is Partial<Listing> & Pick<Listing, 'id' | 'title' | 'rentalMode' | 'images' | 'publishedAt'> {
  if (!value || typeof value !== 'object') return false
  const listing = value as Record<string, unknown>
  const coordinates = listing.coordinates as Record<string, unknown> | undefined
  return typeof listing.id === 'string'
    && typeof listing.title === 'string'
    && typeof listing.city === 'string'
    && typeof listing.area === 'string'
    && typeof listing.price === 'number'
    && Number.isFinite(listing.price)
    && (listing.rentalMode === 'long' || listing.rentalMode === 'holiday')
    && Array.isArray(listing.images)
    && listing.images.every((image) => typeof image === 'string')
    && typeof listing.publishedAt === 'string'
    && typeof listing.expiresAt === 'string'
    && Boolean(coordinates)
    && typeof coordinates?.lat === 'number'
    && Number.isFinite(coordinates.lat)
    && typeof coordinates?.lng === 'number'
    && Number.isFinite(coordinates.lng)
}

export function normalizeListing(value: unknown): Listing | null {
  if (!isListingLike(value)) return null
  const legacy = value as LegacyListing
  const rentalMode = value.rentalMode
  const tenantRequirement = inferTenantRequirement(legacy)
  const roomCapacity: 1 | 2 = legacy.roomCapacity === 2 || (!legacy.roomCapacity && tenantRequirement === 'couple') ? 2 : 1
  const price = typeof legacy.price === 'number' ? legacy.price : 0
  const monthlyPrice = typeof legacy.monthlyPrice === 'number'
    ? legacy.monthlyPrice
    : rentalMode === 'long' ? price : undefined
  const nightlyPrice = typeof legacy.nightlyPrice === 'number'
    ? legacy.nightlyPrice
    : rentalMode === 'holiday' ? price : undefined
  const listing: Listing = {
    id: value.id,
    title: value.title,
    city: legacy.city ?? 'Tenerife',
    area: legacy.area ?? 'Tenerife',
    approximateAddress: legacy.approximateAddress ?? `${legacy.area ?? 'Tenerife'} · ubicación aproximada`,
    price: rentalMode === 'holiday' ? nightlyPrice ?? price : monthlyPrice ?? price,
    cadence: rentalMode === 'holiday' ? 'noche' : 'mes',
    monthlyPrice,
    nightlyPrice,
    weeklyPrice: legacy.weeklyPrice,
    rentalMode,
    roomType: legacy.roomType ?? 'Habitación individual',
    available: legacy.available ?? 'Consultar disponibilidad',
    availableFrom: legacy.availableFrom ?? new Date().toISOString().slice(0, 10),
    availableUntil: legacy.availableUntil,
    minimumStay: legacy.minimumStay ?? (rentalMode === 'holiday' ? 'Mínimo 1 noche' : 'Mínimo 1 mes'),
    minimumStayMonths: typeof legacy.minimumStayMonths === 'number' ? legacy.minimumStayMonths : rentalMode === 'long' ? 1 : 0,
    minimumNights: typeof legacy.minimumNights === 'number' ? legacy.minimumNights : rentalMode === 'holiday' ? 1 : undefined,
    deposit: legacy.deposit ?? 'Sin fianza',
    depositAmount: typeof legacy.depositAmount === 'number' ? legacy.depositAmount : 0,
    bills: legacy.bills ?? 'Gastos no especificados',
    billsIncluded: Boolean(legacy.billsIncluded),
    bathroom: legacy.bathroom ?? 'Baño compartido',
    kitchen: legacy.kitchen ?? 'Cocina compartida',
    furnished: legacy.furnished ?? true,
    roomSizeM2: typeof legacy.roomSizeM2 === 'number' ? legacy.roomSizeM2 : typeof legacy.size === 'number' ? legacy.size : 12,
    currentResidents: typeof legacy.currentResidents === 'number' ? legacy.currentResidents : typeof legacy.occupants === 'number' ? legacy.occupants : 1,
    roomCapacity,
    shower: legacy.shower === 'Ducha privada' ? 'Ducha privada' : 'Ducha compartida',
    coordinates: legacy.coordinates && typeof legacy.coordinates.lat === 'number' && typeof legacy.coordinates.lng === 'number'
      ? legacy.coordinates
      : { ...TENERIFE_CENTER },
    tenantRequirement,
    smokingAllowed: Boolean(legacy.smokingAllowed),
    petsAllowed: Boolean(legacy.petsAllowed),
    childrenAllowed: Boolean(legacy.childrenAllowed),
    empadronamientoAllowed: Boolean(legacy.empadronamientoAllowed),
    restrictions: Array.isArray(legacy.restrictions) ? legacy.restrictions : [],
    amenities: Array.isArray(legacy.amenities) ? legacy.amenities : [],
    description: legacy.description ?? '',
    homeDescription: legacy.homeDescription ?? '',
    images: value.images,
    owner: legacy.owner ?? { name: 'Anunciante', initials: 'AN', since: 'Cuenta local', response: 'Consulta disponibilidad', verified: false },
    advertiserType: legacy.advertiserType ?? 'Particular',
    source: legacy.source,
    status: legacy.status ?? 'Publicado',
    publishedAt: value.publishedAt,
    views: typeof legacy.views === 'number' ? legacy.views : 0,
    expiresAt: legacy.expiresAt ?? '2099-12-31',
    userCreated: legacy.userCreated,
    ownerUserId: legacy.ownerUserId ?? (legacy.userCreated ? 'host-demo' : undefined),
    contactPhone: legacy.contactPhone,
    contactWhatsapp: legacy.contactWhatsapp ?? legacy.contactPhone,
    contactEmail: legacy.contactEmail,
    showPhone: legacy.showPhone ?? true,
    showWhatsApp: legacy.showWhatsApp ?? true,
    allowContactForm: legacy.allowContactForm ?? true,
    closedReason: legacy.closedReason,
  }
  listing.restrictions = getCriticalRestrictions(listing)
  return expireListing(listing)
}

export function expireListing(listing: Listing, now = new Date()): Listing {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const expires = new Date(`${listing.expiresAt}T00:00:00`).getTime()
  if (listing.status === 'Publicado' && Number.isFinite(expires) && expires < today) {
    return { ...listing, status: 'Finalizado', closedReason: 'expired' }
  }
  return listing
}

export function isPublicListing(listing: Listing) {
  return expireListing(listing).status === 'Publicado'
}
