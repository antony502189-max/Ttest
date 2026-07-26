import type { Listing } from '@/types'
import { normalizeTenerifeText } from '@/lib/tenerife'

export type ZoneKind = 'municipality' | 'district' | 'neighbourhood'

export interface TenerifeZoneProperties {
  id: string
  label: string
  kind: ZoneKind
  parentId?: string
  aliases?: string[]
  geometryAvailable?: boolean
  nationalCode?: string
  sourceId?: string
  source?: string
}

export interface TenerifeZoneFeature {
  type: 'Feature'
  id: string
  properties: TenerifeZoneProperties
  geometry: TenerifeZoneGeometry
}

export type TenerifeZoneGeometry =
  | { type: 'Polygon'; coordinates: number[][][] }
  | { type: 'MultiPolygon'; coordinates: number[][][][] }

export interface TenerifeZoneCollection {
  type: 'FeatureCollection'
  attribution?: string
  retrieved?: string
  sources?: Array<{ id: string; url: string; license: string; legalPrecision: string }>
  features: TenerifeZoneFeature[]
}

export const TENERIFE_MUNICIPALITIES = [
  'Adeje', 'Arafo', 'Arico', 'Arona', 'Buenavista del Norte', 'Candelaria', 'El Rosario',
  'El Sauzal', 'El Tanque', 'Fasnia', 'Garachico', 'Granadilla de Abona', 'Guía de Isora',
  'Güímar', 'Icod de los Vinos', 'La Guancha', 'La Matanza de Acentejo', 'La Orotava',
  'La Victoria de Acentejo', 'Los Realejos', 'Los Silos', 'Puerto de la Cruz',
  'San Cristóbal de La Laguna', 'San Juan de la Rambla', 'San Miguel de Abona',
  'Santa Cruz de Tenerife', 'Santa Úrsula', 'Santiago del Teide', 'Tacoronte', 'Tegueste',
  'Vilaflor de Chasna',
] as const

export const slugifyZone = (value: string) => normalizeTenerifeText(value).replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')

const labelById = new Map(TENERIFE_MUNICIPALITIES.map((label) => [slugifyZone(label), label]))

export const municipalityZoneId = (value: string) => `municipality:${slugifyZone(value)}`

export function canonicalizeZoneId(value: string) {
  const trimmed = value.trim()
  if (/^(municipality|district|neighbourhood):[a-z0-9:-]+$/.test(trimmed)) return trimmed
  const slug = slugifyZone(trimmed)
  return labelById.has(slug) ? `municipality:${slug}` : trimmed
}

export const isDetailedZoneId = (value: string) => /^(district|neighbourhood):/.test(canonicalizeZoneId(value))

export function zoneKindFromId(value: string): ZoneKind | null {
  const kind = canonicalizeZoneId(value).split(':', 1)[0]
  return kind === 'municipality' || kind === 'district' || kind === 'neighbourhood' ? kind : null
}

export function getMunicipalityLabel(id: string) {
  const canonical = canonicalizeZoneId(id)
  const slug = canonical.startsWith('municipality:') ? canonical.slice('municipality:'.length) : slugifyZone(canonical)
  return labelById.get(slug)
}

export function getMunicipalityId(label: string) {
  const id = slugifyZone(label)
  return labelById.has(id) ? municipalityZoneId(id) : undefined
}

const pointInRing = (point: { lat: number; lng: number }, ring: number[][]) => {
  let inside = false
  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index++) {
    const [x, y] = ring[index]
    const [previousX, previousY] = ring[previous]
    const intersects = (y > point.lat) !== (previousY > point.lat)
      && point.lng < ((previousX - x) * (point.lat - y)) / (previousY - y || Number.EPSILON) + x
    if (intersects) inside = !inside
  }
  return inside
}

function pointInGeometry(point: { lat: number; lng: number }, geometry: TenerifeZoneGeometry) {
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates
  return polygons.some((polygon) => pointInRing(point, polygon[0]) && !polygon.slice(1).some((hole) => pointInRing(point, hole)))
}

export function getZoneFeature(zoneId: string, collection?: TenerifeZoneCollection | null) {
  const canonical = canonicalizeZoneId(zoneId)
  return collection?.features.find((feature) => feature.properties.id === canonical)
}

export function getZoneLabel(zoneId: string, collection?: TenerifeZoneCollection | null) {
  return getMunicipalityLabel(zoneId) ?? getZoneFeature(zoneId, collection)?.properties.label ?? zoneId
}

export function getRootMunicipalityId(zoneId: string, collection?: TenerifeZoneCollection | null) {
  let current = canonicalizeZoneId(zoneId)
  const visited = new Set<string>()
  while (!current.startsWith('municipality:') && !visited.has(current)) {
    visited.add(current)
    const parentId = getZoneFeature(current, collection)?.properties.parentId
    if (!parentId) {
      const municipalitySlug = current.split(':')[1]
      return municipalitySlug ? `municipality:${municipalitySlug}` : undefined
    }
    current = canonicalizeZoneId(parentId)
  }
  return current.startsWith('municipality:') ? current : undefined
}

export function listingMatchesSelectedAreas(listing: Listing, areas: string[], collection?: TenerifeZoneCollection | null) {
  if (!areas.length) return true
  const municipalityId = getMunicipalityId(listing.city)
  return areas.some((area) => {
    const canonical = canonicalizeZoneId(area)
    if (canonical.startsWith('municipality:')) return canonical === municipalityId
    const feature = getZoneFeature(canonical, collection)
    if (feature) return pointInGeometry(listing.coordinates, feature.geometry)
    if (canonical.startsWith('district:') || canonical.startsWith('neighbourhood:')) {
      return canonical.includes(`:${slugifyZone(listing.city)}:`)
    }
    return slugifyZone(area) === slugifyZone(listing.area)
  })
}

export function countListingsByMunicipality(listings: Listing[]) {
  const counts = new Map<string, number>()
  listings.forEach((listing) => {
    const id = getMunicipalityId(listing.city)
    if (id) counts.set(id, (counts.get(id) ?? 0) + 1)
  })
  return counts
}

export function countListingsForZones(listings: Listing[], zoneIds: string[], collection?: TenerifeZoneCollection | null) {
  if (!zoneIds.length) return listings.length
  return listings.filter((listing) => listingMatchesSelectedAreas(listing, zoneIds, collection)).length
}

export function countListingsForZone(listings: Listing[], zoneId: string, collection?: TenerifeZoneCollection | null) {
  return listings.filter((listing) => listingMatchesSelectedAreas(listing, [zoneId], collection)).length
}
