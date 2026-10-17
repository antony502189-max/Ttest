import names from '@/data/spain-provinces.json'
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
