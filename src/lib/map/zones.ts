import type { Listing } from '@/types'
import { normalizeTenerifeText } from '@/lib/tenerife'

export interface TenerifeZoneProperties {
  id: string
  label: string
  kind: 'municipality' | 'district' | 'area'
  parentId?: string
  nationalCode?: string
}

export interface TenerifeZoneFeature {
  type: 'Feature'
  id: string
  properties: TenerifeZoneProperties
  geometry: {
    type: 'MultiPolygon'
    coordinates: number[][][][]
  }
}

export interface TenerifeZoneCollection {
  type: 'FeatureCollection'
  attribution?: string
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

export function getMunicipalityLabel(id: string) {
  return labelById.get(slugifyZone(id))
}

export function getMunicipalityId(label: string) {
  const id = slugifyZone(label)
  return labelById.has(id) ? id : undefined
}

export function listingMatchesSelectedAreas(listing: Listing, areas: string[]) {
  if (!areas.length) return true
  const municipalityId = getMunicipalityId(listing.city)
  return areas.some((area) => area === listing.area || slugifyZone(area) === municipalityId)
}

export function countListingsByMunicipality(listings: Listing[]) {
  const counts = new Map<string, number>()
  listings.forEach((listing) => {
    const id = getMunicipalityId(listing.city)
    if (id) counts.set(id, (counts.get(id) ?? 0) + 1)
  })
  return counts
}

export function countListingsForZones(listings: Listing[], zoneIds: string[]) {
  if (!zoneIds.length) return listings.length
  const selected = new Set(zoneIds.map(slugifyZone))
  return listings.filter((listing) => {
    const id = getMunicipalityId(listing.city)
    return Boolean(id && selected.has(id))
  }).length
}
