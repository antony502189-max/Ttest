import type { Coordinates, Listing } from '@/types'

export const TENERIFE_CENTER = { lat: 28.2916, lng: -16.6291 } as const
export const TENERIFE_DEFAULT_ZOOM = 9
export const TENERIFE_BOUNDS = { south: 27.92, west: -17.02, north: 28.68, east: -16.01 } as const

export type TenerifeLocationType = 'island' | 'municipality' | 'district' | 'area'

export interface TenerifeLocation {
  type: TenerifeLocationType
  label: string
  normalizedValue: string
  aliases?: string[]
  coordinates?: Coordinates
}

const municipalityNames = [
  'Adeje', 'Arafo', 'Arico', 'Arona', 'Buenavista del Norte', 'Candelaria', 'El Rosario',
  'El Sauzal', 'El Tanque', 'Fasnia', 'Garachico', 'Granadilla de Abona', 'Guía de Isora',
  'Güímar', 'Icod de los Vinos', 'La Guancha', 'La Matanza de Acentejo', 'La Orotava',
  'La Victoria de Acentejo', 'Los Realejos', 'Los Silos', 'Puerto de la Cruz',
  'San Cristóbal de La Laguna', 'San Juan de la Rambla', 'San Miguel de Abona', 'Santa Cruz de Tenerife',
  'Santa Úrsula', 'Santiago del Teide', 'Tacoronte', 'Tegueste', 'Vilaflor de Chasna',
] as const

const knownCoordinates: Record<string, Coordinates> = {
  Adeje: { lat: 28.1227, lng: -16.7244 },
  Arona: { lat: 28.0996, lng: -16.6809 },
  'Granadilla de Abona': { lat: 28.1188, lng: -16.5760 },
  'San Cristóbal de La Laguna': { lat: 28.4874, lng: -16.3159 },
  'Santa Cruz de Tenerife': { lat: 28.4636, lng: -16.2518 },
}

const municipalities: TenerifeLocation[] = municipalityNames.map((label) => ({
  type: 'municipality',
  label,
  normalizedValue: label,
  coordinates: knownCoordinates[label],
  aliases: label === 'Santa Cruz de Tenerife'
    ? ['Santa Cruz']
    : label === 'San Cristóbal de La Laguna'
      ? ['La Laguna', 'San Cristóbal de Laguna']
      : undefined,
}))

const localAreas: TenerifeLocation[] = [
  { type: 'area', label: 'Armeñime', normalizedValue: 'Armeñime', coordinates: { lat: 28.1272, lng: -16.7390 } },
  { type: 'area', label: 'Costa Adeje', normalizedValue: 'Costa Adeje', coordinates: { lat: 28.0902, lng: -16.7260 } },
  { type: 'area', label: 'El Médano', normalizedValue: 'El Médano', coordinates: { lat: 28.0477, lng: -16.5363 }, aliases: ['Medano'] },
  { type: 'area', label: 'Los Cristianos', normalizedValue: 'Los Cristianos', coordinates: { lat: 28.0509, lng: -16.7172 } },
  { type: 'area', label: 'Playa de las Américas', normalizedValue: 'Playa de las Américas', coordinates: { lat: 28.0640, lng: -16.7310 }, aliases: ['Las Américas', 'Playa de las Americas'] },
  { type: 'area', label: 'San Isidro', normalizedValue: 'San Isidro', coordinates: { lat: 28.0770, lng: -16.5580 } },
]

export const TENERIFE_LOCATIONS: TenerifeLocation[] = [
  { type: 'island', label: 'Tenerife', normalizedValue: 'Tenerife', aliases: ['Isla de Tenerife', 'Tenerife isla'], coordinates: TENERIFE_CENTER },
  ...municipalities,
  ...localAreas,
]

export function normalizeTenerifeText(value: string) {
  return value.trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es-ES').replace(/\s+/g, ' ')
}

const locationLookup = new Map(
  TENERIFE_LOCATIONS.flatMap((location) => [location.label, location.normalizedValue, ...(location.aliases ?? [])]
    .map((value) => [normalizeTenerifeText(value), location] as const)),
)

export function resolveTenerifeLocation(value: string) {
  return locationLookup.get(normalizeTenerifeText(value))
}

export function isSupportedTenerifeQuery(value: string) {
  return Boolean(resolveTenerifeLocation(value || 'Tenerife'))
}

export function sanitizeTenerifeHistory(values: string[]) {
  const seen = new Set<string>()
  return values.flatMap((value) => {
    const location = resolveTenerifeLocation(value)
    if (!location || seen.has(location.normalizedValue)) return []
    seen.add(location.normalizedValue)
    return [location.normalizedValue]
  }).slice(0, 8)
}

export function listingMatchesTenerifeLocation(listing: Listing, location?: TenerifeLocation) {
  if (!location || location.type === 'island') return true
  const expected = normalizeTenerifeText(location.normalizedValue)
  return location.type === 'municipality'
    ? normalizeTenerifeText(listing.city) === expected
    : normalizeTenerifeText(listing.area) === expected
}

export function isInsideTenerife(coordinates: Coordinates) {
  return coordinates.lat >= TENERIFE_BOUNDS.south
    && coordinates.lat <= TENERIFE_BOUNDS.north
    && coordinates.lng >= TENERIFE_BOUNDS.west
    && coordinates.lng <= TENERIFE_BOUNDS.east
}
