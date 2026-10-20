import names from '@/data/spain-provinces.json' with { type: 'json' }
import bounds from '@/data/spain-province-bounds.json' with { type: 'json' }
import type { Listing } from '@/types'

// INE province codes: https://www.ine.es/daco/daco42/codmun/cod_provincia.htm
export const SPANISH_PROVINCES = Object.entries(names).map(([id, es]) => ({ id, es }))
export const getProvince = (code: string | null | undefined) => SPANISH_PROVINCES.find((province) => province.id === code)
export const provinceName = (code: string | null | undefined) => getProvince(code)?.es ?? ''
export const resolveProvince = (value: string) => {
  const term = normalize(value)
  return SPANISH_PROVINCES.find((province) => normalize(province.es) === term || province.id === term
    || (province.id === '38' && term === 'tenerife') || (province.id === '07' && term === 'baleares'))
}
export function provinceFromPostcode(postcode?: string) {
  const value = postcode?.trim() ?? ''
  return /^[0-9]{5}$/.test(value) ? getProvince(value.slice(0, 2)) : undefined
}
const normalize = (value: string) => value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim()
export function provinceSuggestions(query: string) {
  const term = normalize(query)
  return SPANISH_PROVINCES.filter((province) => normalize(province.es).includes(term) || province.id.startsWith(term))
    .sort((a, b) => a.es.localeCompare(b.es, 'es'))
}
export function listingInProvince(listing: Listing, code: string) {
  return (listing.provinceCode ?? provinceFromPostcode(listing.postcode)?.id) === code
}

// Rectangles derived from click_that_hood Spain province geometry (MIT),
// https://github.com/codeforgermany/click_that_hood/blob/main/public/data/spain-provinces.geojson
export function provinceMapCamera(code: string, width: number, height: number) {
  const box = (bounds as Record<string, { north: number; south: number; east: number; west: number }>)[code]
  if (!box) return undefined
  const y = (lat: number) => (1 - Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)) / Math.PI) / 2
  const top = y(box.north), bottom = y(box.south)
  const zoom = Math.min(Math.log2(Math.max(240, width) * .85 / (256 * (box.east - box.west) / 360)),
    Math.log2(Math.max(240, height) * .85 / (256 * (bottom - top))))
  return { lat: Math.atan(Math.sinh(Math.PI * (1 - top - bottom))) * 180 / Math.PI,
    lng: (box.east + box.west) / 2, zoom: Math.max(3, Math.min(16, zoom)) }
}
