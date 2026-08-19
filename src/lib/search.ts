import { defaultFilters } from '@/data/listings'
import { getPrimaryPrice, isPublicListing } from '@/lib/listings'
import { canonicalizeZoneId, listingMatchesSelectedAreas, type TenerifeZoneCollection } from '@/lib/map/zones'
import type { Filters, Listing, MapPolygonPoint, RentalMode, TenantRequirement, YesNoAny } from '@/types'

const boolMatches = (value: boolean | null | undefined, filter: YesNoAny) => filter === 'Cualquiera' || (value != null && value === (filter === 'Sí'))
const tenantRequirementValues = new Set<TenantRequirement>(['single-man', 'single-woman', 'single-person', 'couple', 'any'])

function normalizeTenantRequirements(value: unknown): TenantRequirement[] {
  if (!Array.isArray(value)) return []
  return [...new Set(value.filter((item): item is TenantRequirement => typeof item === 'string' && tenantRequirementValues.has(item as TenantRequirement)))]
}

export function getTenantRequirements(filters: Filters): TenantRequirement[] {
  if (filters.tenantRequirement === 'any') return []
  if (filters.tenantRequirement !== 'Cualquiera') return [filters.tenantRequirement]
  return normalizeTenantRequirements(filters.tenantRequirements)
}

export function normalizeFilters(value: unknown): Filters {
  const source = value && typeof value === 'object' ? value as Record<string, unknown> : {}
  const next: Filters = { ...defaultFilters, areas: [], conditions: [], tenantRequirements: [], acceptedTenantTypes: [], amenities: [] }
  for (const key of Object.keys(defaultFilters) as (keyof Filters)[]) {
    const candidate = source[key]
    const fallback = defaultFilters[key]
    if (Array.isArray(fallback)) {
      if (Array.isArray(candidate) && candidate.every((item) => typeof item === 'string')) (next[key] as string[]) = candidate
    } else if (typeof candidate === typeof fallback) {
      ;(next as unknown as Record<string, unknown>)[key] = candidate
    }
  }
  next.tenantRequirements = normalizeTenantRequirements(next.tenantRequirements)
  if (next.tenantRequirement !== 'Cualquiera') next.tenantRequirements = []
  if (!source.tenantRequirement && !source.tenantRequirements) {
    if (source.gender === 'Solo hombre') next.tenantRequirement = 'single-man'
    else if (source.gender === 'Solo mujer') next.tenantRequirement = 'single-woman'
    else if (source.couples === 'Sí') next.tenantRequirement = 'couple'
  }
  if (!source.currentResidents && source.occupants === '5 o más') next.currentResidents = '5+'
  return next
}

export function filterListings(items: Listing[], mode: RentalMode, filters: Filters, zoneCollection?: TenerifeZoneCollection | null) {
  const today = Date.now()
  const tenantRequirements = getTenantRequirements(filters)
  const priceFilterActive = filters.minPrice !== defaultFilters.minPrice || filters.maxPrice !== defaultFilters.maxPrice
  const roomSizeFilterActive = filters.roomSizeMin !== defaultFilters.roomSizeMin || filters.roomSizeMax !== defaultFilters.roomSizeMax
  const homeSizeFilterActive = filters.homeSizeMin !== defaultFilters.homeSizeMin || filters.homeSizeMax !== defaultFilters.homeSizeMax
  return items.filter((listing) => {
    if (!isPublicListing(listing) || listing.rentalMode !== mode) return false
    const primaryPrice = getPrimaryPrice(listing)
    if (priceFilterActive && (primaryPrice < filters.minPrice || primaryPrice > filters.maxPrice)) return false
    if (!listingMatchesSelectedAreas(listing, filters.areas, zoneCollection)) return false
    if (filters.roomType !== 'Cualquiera' && listing.roomType !== filters.roomType) return false
    if (filters.available) {
      if (listing.availableFrom > filters.available) return false
      if (listing.availableUntil && listing.availableUntil < filters.available) return false
    }
    if (filters.availableUntil && listing.availableUntil && listing.availableUntil < filters.availableUntil) return false
    if (filters.minStay !== 'Cualquiera') {
      const requested = Number(filters.minStay)
      if (listing.minimumStayMonths == null || listing.minimumStayMonths > requested) return false
    }
    if (filters.conditions.length && !filters.conditions.every((condition) => listing.restrictions.includes(condition))) return false
    if (tenantRequirements.length && (listing.tenantRequirement == null || !tenantRequirements.includes(listing.tenantRequirement))) return false
    if (filters.bathroom !== 'Cualquiera' && listing.bathroom !== filters.bathroom) return false
    if (filters.kitchen !== 'Cualquiera' && listing.kitchen !== filters.kitchen) return false
    if (filters.furnished && !listing.furnished) return false
    if (filters.billsIncluded && !listing.billsIncluded) return false
    if (filters.deposit !== 'Cualquiera' && listing.depositAmount == null) return false
    if (filters.deposit === 'Sin fianza' && listing.depositAmount !== 0) return false
    if (filters.deposit === 'Hasta 1 mes' && listing.depositAmount != null && listing.depositAmount > primaryPrice) return false
    if (filters.deposit === 'Más de 1 mes' && listing.depositAmount != null && listing.depositAmount <= primaryPrice) return false
    if (roomSizeFilterActive && (listing.roomSizeM2 == null || listing.roomSizeM2 < filters.roomSizeMin || listing.roomSizeM2 > filters.roomSizeMax)) return false
    if (homeSizeFilterActive && (listing.homeSizeM2 == null || listing.homeSizeM2 < filters.homeSizeMin || listing.homeSizeM2 > filters.homeSizeMax)) return false
    if (filters.bathroomCountMin > 0 && (listing.bathroomCount == null || listing.bathroomCount < filters.bathroomCountMin)) return false
    if (filters.rentalUnit !== 'Cualquiera' && listing.rentalUnit !== filters.rentalUnit) return false
    if (filters.bedType !== 'Cualquiera' && listing.bedType !== filters.bedType) return false
    if (filters.bedCountMin > 0 && (listing.bedCount == null || listing.bedCount < filters.bedCountMin)) return false
    if (filters.shower !== 'Cualquiera' && listing.shower !== filters.shower) return false
    if (filters.toilet !== 'Cualquiera' && listing.toilet !== filters.toilet) return false
    if (filters.currentResidents === '5+' && listing.currentResidents < 5) return false
    if (filters.currentResidents !== 'Cualquiera' && filters.currentResidents !== '5+' && listing.currentResidents !== Number(filters.currentResidents)) return false
    if (filters.roomResidents !== 'Cualquiera' && listing.currentRoomResidents !== Number(filters.roomResidents)) return false
    if (filters.roomCapacity !== 'Cualquiera' && listing.roomCapacity !== Number(filters.roomCapacity)) return false
    if (filters.availableSpotsMin > 0) {
      const availableSpots = listing.availableSpots ?? (listing.roomCapacity != null && listing.currentRoomResidents != null ? listing.roomCapacity - listing.currentRoomResidents : null)
      if (availableSpots == null || availableSpots < filters.availableSpotsMin) return false
    }
    if (mode === 'holiday' && filters.minimumNights > 0 && (listing.minimumNights == null || listing.minimumNights > filters.minimumNights)) return false
    if (!boolMatches(listing.smokingAllowed, filters.smoking)) return false
    if (!boolMatches(listing.petsAllowed, filters.pets)) return false
    if (!boolMatches(listing.childrenAllowed, filters.children)) return false
    if (!boolMatches(listing.couplesAllowed, filters.couplesAllowed)) return false
    if (filters.householdGender !== 'Cualquiera' && listing.householdGender !== filters.householdGender) return false
    if (!boolMatches(listing.householdHasChildren, filters.householdHasChildren)) return false
    if (filters.heatingType !== 'Cualquiera' && listing.heatingType !== filters.heatingType) return false
    if (!boolMatches(listing.accessible, filters.accessible)) return false
    if (filters.floor !== 'Cualquiera' && listing.floor !== filters.floor) return false
    if (filters.acceptedTenantTypes.length) {
      const accepted = listing.acceptedTenantTypes ?? []
      if (!filters.acceptedTenantTypes.some((type) => accepted.includes(type))) return false
    }
    if (!boolMatches(listing.empadronamientoAllowed, filters.empadronamiento)) return false
    if (filters.advertiserType !== 'Cualquiera' && listing.advertiserType !== filters.advertiserType) return false
    if (filters.amenities.length && !filters.amenities.every((amenity) => listing.amenities.includes(amenity))) return false
    if (filters.publicationDate !== 'Cualquiera') {
      const ageDays = (today - new Date(listing.publishedAt).getTime()) / 86_400_000
      const limit = filters.publicationDate === '24h' ? 1 : filters.publicationDate === '7d' ? 7 : 30
      if (ageDays > limit) return false
    }
    return true
  })
}

export function sortListings(items: Listing[], sort: string) {
  return items.map((listing, index) => ({ listing, index })).sort((a, b) => {
    if (sort === 'Más recientes') return new Date(b.listing.publishedAt).getTime() - new Date(a.listing.publishedAt).getTime() || a.index - b.index
    if (sort === 'Más antiguos') return new Date(a.listing.publishedAt).getTime() - new Date(b.listing.publishedAt).getTime() || a.index - b.index
    if (sort === 'Precio más bajo') return getPrimaryPrice(a.listing) - getPrimaryPrice(b.listing) || a.index - b.index
    if (sort === 'Precio más alto') return getPrimaryPrice(b.listing) - getPrimaryPrice(a.listing) || a.index - b.index
    return a.index - b.index
  }).map(({ listing }) => listing)
}

export function getActiveFilterKeys(filters: Filters) {
  const keys: string[] = []
  if (filters.minPrice !== defaultFilters.minPrice || filters.maxPrice !== defaultFilters.maxPrice) keys.push('price')
  if (filters.areas.length) keys.push('areas')
  if (filters.roomType !== defaultFilters.roomType) keys.push('roomType')
  if (filters.available) keys.push('available')
  if (filters.availableUntil) keys.push('availableUntil')
  if (filters.minStay !== defaultFilters.minStay) keys.push('minStay')
  if (filters.conditions.length) keys.push('conditions')
  if (getTenantRequirements(filters).length) keys.push('tenantRequirement')
  if (filters.bathroom !== defaultFilters.bathroom) keys.push('bathroom')
  if (filters.kitchen !== defaultFilters.kitchen) keys.push('kitchen')
  if (filters.furnished) keys.push('furnished')
  if (filters.billsIncluded) keys.push('billsIncluded')
  if (filters.deposit !== defaultFilters.deposit) keys.push('deposit')
  if (filters.roomSizeMin !== defaultFilters.roomSizeMin || filters.roomSizeMax !== defaultFilters.roomSizeMax) keys.push('roomSize')
  if (filters.homeSizeMin !== defaultFilters.homeSizeMin || filters.homeSizeMax !== defaultFilters.homeSizeMax) keys.push('homeSize')
  if (filters.bathroomCountMin !== defaultFilters.bathroomCountMin) keys.push('bathroomCount')
  if (filters.rentalUnit !== defaultFilters.rentalUnit) keys.push('rentalUnit')
  if (filters.bedType !== defaultFilters.bedType) keys.push('bedType')
  if (filters.bedCountMin !== defaultFilters.bedCountMin) keys.push('bedCount')
  if (filters.shower !== defaultFilters.shower) keys.push('shower')
  if (filters.toilet !== defaultFilters.toilet) keys.push('toilet')
  if (filters.currentResidents !== defaultFilters.currentResidents) keys.push('currentResidents')
  if (filters.roomResidents !== defaultFilters.roomResidents) keys.push('roomResidents')
  if (filters.roomCapacity !== defaultFilters.roomCapacity) keys.push('roomCapacity')
  if (filters.availableSpotsMin !== defaultFilters.availableSpotsMin) keys.push('availableSpots')
  if (filters.minimumNights !== defaultFilters.minimumNights) keys.push('minimumNights')
  if (filters.smoking !== defaultFilters.smoking) keys.push('smoking')
  if (filters.pets !== defaultFilters.pets) keys.push('pets')
  if (filters.children !== defaultFilters.children) keys.push('children')
  if (filters.couplesAllowed !== defaultFilters.couplesAllowed) keys.push('couplesAllowed')
  if (filters.householdGender !== defaultFilters.householdGender) keys.push('householdGender')
  if (filters.householdHasChildren !== defaultFilters.householdHasChildren) keys.push('householdHasChildren')
  if (filters.heatingType !== defaultFilters.heatingType) keys.push('heatingType')
  if (filters.accessible !== defaultFilters.accessible) keys.push('accessible')
  if (filters.floor !== defaultFilters.floor) keys.push('floor')
  if (filters.acceptedTenantTypes.length) keys.push('acceptedTenantTypes')
  if (filters.empadronamiento !== defaultFilters.empadronamiento) keys.push('empadronamiento')
  if (filters.publicationDate !== defaultFilters.publicationDate) keys.push('publicationDate')
  if (filters.advertiserType !== defaultFilters.advertiserType) keys.push('advertiserType')
  if (filters.amenities.length) keys.push('amenities')
  return keys
}

const listFields: (keyof Filters)[] = ['areas', 'conditions', 'tenantRequirements', 'acceptedTenantTypes', 'amenities']
const booleanFields: (keyof Filters)[] = ['furnished', 'billsIncluded']
const numericFields: (keyof Filters)[] = [
  'minPrice', 'maxPrice', 'roomSizeMin', 'roomSizeMax', 'homeSizeMin', 'homeSizeMax',
  'bathroomCountMin', 'bedCountMin', 'availableSpotsMin', 'minimumNights',
]
const paramNames: Partial<Record<keyof Filters, string>> = {
  minPrice: 'precioMin', maxPrice: 'precioMax', areas: 'zonas', roomType: 'habitacion', available: 'fecha', availableUntil: 'hasta', minStay: 'estancia', conditions: 'condiciones', tenantRequirement: 'requisito', tenantRequirements: 'requisitos',
  bathroom: 'bano', kitchen: 'cocina', furnished: 'amueblada', billsIncluded: 'gastos', deposit: 'fianza', smoking: 'fumar', pets: 'mascotas',
  children: 'ninos', couplesAllowed: 'parejasOk', householdGender: 'convivenciaGenero', householdHasChildren: 'convivenciaNinos', heatingType: 'calefaccion', accessible: 'adaptada', floor: 'planta', acceptedTenantTypes: 'acepta',
  empadronamiento: 'padron', publicationDate: 'publicado', advertiserType: 'anunciante', amenities: 'servicios', sort: 'orden',
  roomSizeMin: 'tamanoMin', roomSizeMax: 'tamanoMax', homeSizeMin: 'viviendaMin', homeSizeMax: 'viviendaMax', bathroomCountMin: 'banosMin', rentalUnit: 'unidad', bedType: 'cama', bedCountMin: 'camasMin',
  shower: 'ducha', toilet: 'aseo', currentResidents: 'residentes', roomResidents: 'residentesHabitacion', roomCapacity: 'capacidad', availableSpotsMin: 'plazasMin', minimumNights: 'nochesMin',
}

export function filtersFromParams(params: URLSearchParams): Filters {
  const next: Filters = { ...defaultFilters, areas: [], conditions: [], tenantRequirements: [], acceptedTenantTypes: [], amenities: [] }
  ;(Object.keys(paramNames) as (keyof Filters)[]).forEach((key) => {
    const raw = params.get(paramNames[key] ?? key)
    if (raw === null) return
    if (listFields.includes(key)) {
      const values = raw.split(key === 'areas' ? /[,|]/ : '|').filter(Boolean)
      ;(next[key] as string[]) = key === 'areas' ? values.map(canonicalizeZoneId) : values
    }
    else if (booleanFields.includes(key)) (next[key] as boolean) = raw === '1'
    else if (numericFields.includes(key)) (next[key] as number) = Number(raw)
    else (next[key] as string) = raw
  })
  if (params.has('requisito')) next.tenantRequirements = []
  else if (params.has('requisitos')) next.tenantRequirement = 'Cualquiera'
  if (!params.has('requisito') && !params.has('requisitos')) {
    const legacyGender = params.get('genero')
    const legacyCouples = params.get('parejas')
    if (legacyGender === 'Solo hombre') next.tenantRequirement = 'single-man'
    else if (legacyGender === 'Solo mujer') next.tenantRequirement = 'single-woman'
    else if (legacyCouples === 'Sí') next.tenantRequirement = 'couple'
  }
  if (!params.has('residentes')) {
    const legacyResidents = params.get('ocupantes')
    if (legacyResidents === '5 o más') next.currentResidents = '5+'
  }
  return normalizeFilters(next)
}

export function filtersToParams(filters: Filters, params = new URLSearchParams()) {
  const normalized = normalizeFilters(filters)
  if (normalized.tenantRequirement !== 'Cualquiera') normalized.tenantRequirements = []
  ;['genero', 'parejas', 'ocupantes'].forEach((name) => params.delete(name))
  ;(Object.keys(paramNames) as (keyof Filters)[]).forEach((key) => {
    const name = paramNames[key] ?? key
    const value = normalized[key]
    const fallback = defaultFilters[key]
    const isDefault = Array.isArray(value) ? value.length === 0 : value === fallback
    if (isDefault) params.delete(name)
    else if (Array.isArray(value)) params.set(name, (key === 'areas' ? value.map(canonicalizeZoneId) : value).join(key === 'areas' ? ',' : '|'))
    else if (typeof value === 'boolean') params.set(name, value ? '1' : '0')
    else params.set(name, String(value))
  })
  if (normalized.tenantRequirement !== 'Cualquiera') params.delete('requisitos')
  else if (normalized.tenantRequirements.length) params.delete('requisito')
  return params
}

export function pointInPolygon(point: MapPolygonPoint, polygon: MapPolygonPoint[]) {
  let inside = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].lng
    const yi = polygon[i].lat
    const xj = polygon[j].lng
    const yj = polygon[j].lat
    const intersects = (yi > point.lat) !== (yj > point.lat) && point.lng < ((xj - xi) * (point.lat - yi)) / (yj - yi || Number.EPSILON) + xi
    if (intersects) inside = !inside
  }
  return inside
}

export function formatPublishedAt(value: string) {
  const date = new Date(value)
  const days = Math.max(0, Math.floor((Date.now() - date.getTime()) / 86_400_000))
  if (days === 0) return 'Publicado hoy'
  if (days === 1) return 'Publicado ayer'
  return `Publicado hace ${days} días`
}
