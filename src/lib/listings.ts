import type { Listing, TenantRequirement } from '@/types'
import { TENERIFE_CENTER } from '@/lib/tenerife'

export const tenantRequirementLabels: Record<TenantRequirement, string> = {
  'single-man': 'Solo hombre',
  'single-woman': 'Solo mujer',
  'single-person': '1 persona',
  couple: '2 personas (pareja/amigos)',
  any: 'Sin restricciones',
}

export const unknownListingFact = 'Consultar con el anunciante'

export function getPrimaryPrice(listing: Listing) {
  return listing.rentalMode === 'holiday'
    ? listing.nightlyPrice ?? listing.price
    : listing.monthlyPrice ?? listing.price
}

export function getPrimaryCadence(listing: Listing): 'mes' | 'noche' {
  return listing.rentalMode === 'holiday' ? 'noche' : 'mes'
}

export function getBedroomCount(listing: Listing) {
  const explicit = Number(listing.bedroomCount)
  if (Number.isFinite(explicit) && explicit >= 1) return Math.min(99, Math.max(1, Math.round(explicit)))
  if (listing.roomType === 'Estudio') return 1
  return Math.min(99, Math.max(1, Math.round((listing.currentResidents || 1) + 1)))
}

export function getCriticalRestrictions(listing: Listing): string[] {
  const restrictions = [
    listing.tenantRequirement == null ? unknownListingFact : tenantRequirementLabels[listing.tenantRequirement],
    listing.roomCapacity == null ? unknownListingFact : `Habitación para ${listing.roomCapacity} ${listing.roomCapacity === 1 ? 'persona' : 'personas'}`,
    listing.petsAllowed == null ? '' : listing.petsAllowed ? 'Mascotas permitidas' : 'Sin mascotas',
    listing.smokingAllowed == null ? '' : listing.smokingAllowed ? 'Se puede fumar' : 'No fumar',
    listing.childrenAllowed == null ? '' : listing.childrenAllowed ? 'Niños permitidos' : 'Sin niños',
    listing.empadronamientoAllowed == null ? '' : listing.empadronamientoAllowed ? 'Empadronamiento posible' : 'Sin empadronamiento',
    listing.rentalMode === 'holiday'
      ? listing.minimumNights == null ? '' : `Estancia mínima de ${listing.minimumNights} ${listing.minimumNights === 1 ? 'noche' : 'noches'}`
      : listing.minimumStayMonths == null ? '' : `Estancia mínima de ${listing.minimumStayMonths} ${listing.minimumStayMonths === 1 ? 'mes' : 'meses'}`,
    listing.billsIncluded == null ? unknownListingFact : listing.billsIncluded ? 'Gastos incluidos' : listing.bills,
  ]
  return [...new Set(restrictions.filter(Boolean))]
}

export function getImageCriticalRestrictions(listing: Listing): string[] {
  const conditions: string[] = []
  if (listing.tenantRequirement && listing.tenantRequirement !== 'any') conditions.push(tenantRequirementLabels[listing.tenantRequirement])
  if (listing.petsAllowed === false) conditions.push('Sin mascotas')
  if (listing.childrenAllowed === false) conditions.push('Sin niños')
  if (listing.smokingAllowed === false) conditions.push('No fumar')
  if (!conditions.length && listing.roomCapacity === 1) conditions.push('1 persona')
  return [...new Set(conditions)].slice(0, 2)
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

function inferTenantRequirement(listing: LegacyListing): TenantRequirement | null {
  if (listing.tenantRequirement) return listing.tenantRequirement
  if (listing.genderPreference === 'Solo hombre') return 'single-man'
  if (listing.genderPreference === 'Solo mujer') return 'single-woman'
  if (listing.couplesAllowed && listing.roomType !== 'Habitación individual') return 'couple'
  return listing.isExternal ? null : 'any'
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
  const roomCapacity = typeof legacy.roomCapacity === 'number' && legacy.roomCapacity >= 1
    ? Math.round(legacy.roomCapacity)
    : tenantRequirement === 'couple' ? 2 : legacy.isExternal ? null : 1
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
    minimumStay: legacy.minimumStay ?? (legacy.isExternal ? 'Consultar estancia mínima' : rentalMode === 'holiday' ? 'Mínimo 1 noche' : 'Mínimo 1 mes'),
    minimumStayMonths: typeof legacy.minimumStayMonths === 'number' ? legacy.minimumStayMonths : legacy.isExternal ? null : rentalMode === 'long' ? 1 : 0,
    minimumNights: typeof legacy.minimumNights === 'number' ? legacy.minimumNights : legacy.isExternal ? undefined : rentalMode === 'holiday' ? 1 : undefined,
    deposit: legacy.deposit ?? (legacy.isExternal ? unknownListingFact : 'Sin fianza'),
    depositAmount: typeof legacy.depositAmount === 'number' ? legacy.depositAmount : legacy.isExternal ? null : 0,
    bills: legacy.bills ?? (legacy.isExternal ? unknownListingFact : 'Gastos no especificados'),
    billsIncluded: typeof legacy.billsIncluded === 'boolean' ? legacy.billsIncluded : legacy.isExternal ? null : false,
    bathroom: legacy.bathroom ?? (legacy.isExternal ? null : 'Baño compartido'),
    kitchen: legacy.kitchen ?? (legacy.isExternal ? null : 'Cocina compartida'),
    furnished: typeof legacy.furnished === 'boolean' ? legacy.furnished : legacy.isExternal ? null : true,
    roomSizeM2: typeof legacy.roomSizeM2 === 'number' ? legacy.roomSizeM2 : typeof legacy.size === 'number' ? legacy.size : legacy.isExternal ? null : 12,
    bedroomCount: typeof legacy.bedroomCount === 'number' && Number.isFinite(legacy.bedroomCount)
      ? Math.min(99, Math.max(1, Math.round(legacy.bedroomCount)))
      : legacy.roomType === 'Estudio' ? 1 : Math.min(99, Math.max(1, Math.round((legacy.currentResidents ?? legacy.occupants ?? 1) + 1))),
    currentResidents: typeof legacy.currentResidents === 'number' ? legacy.currentResidents : typeof legacy.occupants === 'number' ? legacy.occupants : 1,
    roomCapacity,
    shower: legacy.shower === 'Ducha privada' ? 'Ducha privada' : 'Ducha compartida',
    coordinates: legacy.coordinates && typeof legacy.coordinates.lat === 'number' && typeof legacy.coordinates.lng === 'number'
      ? legacy.coordinates
      : { ...TENERIFE_CENTER },
    tenantRequirement,
    smokingAllowed: typeof legacy.smokingAllowed === 'boolean' ? legacy.smokingAllowed : null,
    petsAllowed: typeof legacy.petsAllowed === 'boolean' ? legacy.petsAllowed : null,
    childrenAllowed: typeof legacy.childrenAllowed === 'boolean' ? legacy.childrenAllowed : null,
    empadronamientoAllowed: typeof legacy.empadronamientoAllowed === 'boolean' ? legacy.empadronamientoAllowed : null,
    restrictions: Array.isArray(legacy.restrictions) ? legacy.restrictions : [],
    amenities: Array.isArray(legacy.amenities) ? legacy.amenities : [],
    description: legacy.description ?? '',
    homeDescription: legacy.homeDescription ?? '',
    images: value.images,
    owner: legacy.owner ?? { name: 'Anunciante', initials: 'AN', since: 'Cuenta local', response: 'Consulta disponibilidad', verified: false },
    advertiserType: legacy.advertiserType ?? 'Particular',
    source: legacy.source,
    isExternal: legacy.isExternal,
    primarySource: legacy.primarySource,
    sourceUrl: legacy.sourceUrl,
    sourcePriceText: legacy.sourcePriceText,
    priceCurrency: legacy.priceCurrency,
    pricePeriod: legacy.pricePeriod,
    priceIsFrom: legacy.priceIsFrom,
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
