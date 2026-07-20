import { defaultFilters } from '@/data/listings'
import { getPrimaryPrice, isPublicListing } from '@/lib/listings'
import type { Filters, Listing, MapPolygonPoint, RentalMode, YesNoAny } from '@/types'

const boolMatches = (value: boolean, filter: YesNoAny) => filter === 'Cualquiera' || value === (filter === 'Sí')

export function filterListings(items: Listing[], mode: RentalMode, filters: Filters) {
  const today = Date.now()
  return items.filter((listing) => {
    if (!isPublicListing(listing) || listing.rentalMode !== mode) return false
    const primaryPrice = getPrimaryPrice(listing)
    if (primaryPrice < filters.minPrice || primaryPrice > filters.maxPrice) return false
    if (filters.areas.length && !filters.areas.includes(listing.area)) return false
    if (filters.roomType !== 'Cualquiera' && listing.roomType !== filters.roomType) return false
    if (filters.available && listing.availableFrom > filters.available) return false
    if (filters.minStay !== 'Cualquiera') {
      const requested = Number(filters.minStay)
      if (listing.minimumStayMonths > requested) return false
    }
    if (filters.conditions.length && !filters.conditions.every((condition) => listing.restrictions.includes(condition))) return false
    if (filters.gender !== 'Cualquiera' && listing.genderPreference !== filters.gender) return false
    if (filters.bathroom !== 'Cualquiera' && listing.bathroom !== filters.bathroom) return false
    if (filters.kitchen !== 'Cualquiera' && listing.kitchen !== filters.kitchen) return false
    if (filters.furnished && !listing.furnished) return false
    if (filters.billsIncluded && !listing.billsIncluded) return false
    if (filters.deposit === 'Sin fianza' && listing.depositAmount !== 0) return false
    if (filters.deposit === 'Hasta 1 mes' && listing.depositAmount > primaryPrice) return false
    if (filters.deposit === 'Más de 1 mes' && listing.depositAmount <= primaryPrice) return false
    if (filters.occupants === '1–2' && listing.currentResidents > 2) return false
    if (filters.occupants === '3–4' && (listing.currentResidents < 3 || listing.currentResidents > 4)) return false
    if (filters.occupants === '5 o más' && listing.currentResidents < 5) return false
    if (listing.roomSizeM2 < filters.roomSizeMin || listing.roomSizeM2 > filters.roomSizeMax) return false
    if (filters.shower !== 'Cualquiera' && listing.shower !== filters.shower) return false
    if (filters.currentResidents !== 'Cualquiera' && listing.currentResidents !== Number(filters.currentResidents)) return false
    if (filters.roomCapacity !== 'Cualquiera' && listing.roomCapacity !== Number(filters.roomCapacity)) return false
    if (mode === 'holiday' && filters.minimumNights > 0 && (listing.minimumNights ?? 1) > filters.minimumNights) return false
    if (mode === 'holiday' && filters.availableUntil && (!listing.availableUntil || listing.availableUntil < filters.availableUntil)) return false
    if (!boolMatches(listing.smokingAllowed, filters.smoking)) return false
    if (!boolMatches(listing.petsAllowed, filters.pets)) return false
    if (!boolMatches(listing.couplesAllowed, filters.couples)) return false
    if (!boolMatches(listing.childrenAllowed, filters.children)) return false
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
  if (filters.minStay !== defaultFilters.minStay) keys.push('minStay')
  if (filters.conditions.length) keys.push('conditions')
  if (filters.gender !== defaultFilters.gender) keys.push('gender')
  if (filters.bathroom !== defaultFilters.bathroom) keys.push('bathroom')
  if (filters.kitchen !== defaultFilters.kitchen) keys.push('kitchen')
  if (filters.furnished) keys.push('furnished')
  if (filters.billsIncluded) keys.push('billsIncluded')
  if (filters.deposit !== defaultFilters.deposit) keys.push('deposit')
  if (filters.occupants !== defaultFilters.occupants) keys.push('occupants')
  if (filters.roomSizeMin !== defaultFilters.roomSizeMin || filters.roomSizeMax !== defaultFilters.roomSizeMax) keys.push('roomSize')
  if (filters.shower !== defaultFilters.shower) keys.push('shower')
  if (filters.currentResidents !== defaultFilters.currentResidents) keys.push('currentResidents')
  if (filters.roomCapacity !== defaultFilters.roomCapacity) keys.push('roomCapacity')
  if (filters.minimumNights !== defaultFilters.minimumNights) keys.push('minimumNights')
  if (filters.availableUntil !== defaultFilters.availableUntil) keys.push('availableUntil')
  if (filters.smoking !== defaultFilters.smoking) keys.push('smoking')
  if (filters.pets !== defaultFilters.pets) keys.push('pets')
  if (filters.couples !== defaultFilters.couples) keys.push('couples')
  if (filters.children !== defaultFilters.children) keys.push('children')
  if (filters.empadronamiento !== defaultFilters.empadronamiento) keys.push('empadronamiento')
  if (filters.publicationDate !== defaultFilters.publicationDate) keys.push('publicationDate')
  if (filters.advertiserType !== defaultFilters.advertiserType) keys.push('advertiserType')
  if (filters.amenities.length) keys.push('amenities')
  return keys
}

const listFields: (keyof Filters)[] = ['areas', 'conditions', 'amenities']
const booleanFields: (keyof Filters)[] = ['furnished', 'billsIncluded']
const numericFields: (keyof Filters)[] = ['minPrice', 'maxPrice', 'roomSizeMin', 'roomSizeMax', 'minimumNights']
const paramNames: Partial<Record<keyof Filters, string>> = {
  minPrice: 'precioMin', maxPrice: 'precioMax', areas: 'zonas', roomType: 'habitacion', available: 'fecha', minStay: 'estancia', conditions: 'condiciones', gender: 'genero',
  bathroom: 'bano', kitchen: 'cocina', furnished: 'amueblada', billsIncluded: 'gastos', deposit: 'fianza', occupants: 'ocupantes', smoking: 'fumar', pets: 'mascotas',
  couples: 'parejas', children: 'ninos', empadronamiento: 'padron', publicationDate: 'publicado', advertiserType: 'anunciante', amenities: 'servicios', sort: 'orden',
  roomSizeMin: 'tamanoMin', roomSizeMax: 'tamanoMax', shower: 'ducha', currentResidents: 'residentes', roomCapacity: 'capacidad', minimumNights: 'nochesMin', availableUntil: 'hasta',
}

export function filtersFromParams(params: URLSearchParams): Filters {
  const next: Filters = { ...defaultFilters, areas: [], conditions: [], amenities: [] }
  ;(Object.keys(paramNames) as (keyof Filters)[]).forEach((key) => {
    const raw = params.get(paramNames[key] ?? key)
    if (raw === null) return
    if (listFields.includes(key)) (next[key] as string[]) = raw.split('|').filter(Boolean)
    else if (booleanFields.includes(key)) (next[key] as boolean) = raw === '1'
    else if (numericFields.includes(key)) (next[key] as number) = Number(raw)
    else (next[key] as string) = raw
  })
  return next
}

export function filtersToParams(filters: Filters, params = new URLSearchParams()) {
  ;(Object.keys(paramNames) as (keyof Filters)[]).forEach((key) => {
    const name = paramNames[key] ?? key
    const value = filters[key]
    const fallback = defaultFilters[key]
    const isDefault = Array.isArray(value) ? value.length === 0 : value === fallback
    if (isDefault) params.delete(name)
    else if (Array.isArray(value)) params.set(name, value.join('|'))
    else if (typeof value === 'boolean') params.set(name, value ? '1' : '0')
    else params.set(name, String(value))
  })
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
