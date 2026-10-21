import catalog from '@/data/spain-municipalities.json' with { type: 'json' }
import { getProvince, SPANISH_PROVINCES } from '@/lib/spain-provinces'
import type { Listing } from '@/types'

export type SearchPlace = { id: string; label: string; type: 'province' | 'municipality'; provinceCode: string }
export const normalizePlace = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es').replace(/\s+/g, ' ').trim()
// INE uses trailing articles ("Orotava, La"); accept both official and natural names.
export function municipalityAliases(label: string) {
  const names = label.split('/').flatMap((name) => {
    const [base, article] = name.split(',').map((part) => part.trim())
    return article ? [name, `${article} ${base}`, base] : [name]
  })
  if (label === 'San Cristóbal de La Laguna') names.push('La Laguna', 'San Cristóbal de Laguna')
  if (label === 'Santa Cruz de Tenerife') names.push('Santa Cruz')
  return names
}
const municipalities: SearchPlace[] = Object.entries(catalog.municipalities).map(([id, name]) => ({
  id, label: municipalityAliases(name.split('/')[0])[name.split('/')[0].includes(',') ? 1 : 0], type: 'municipality', provinceCode: id.slice(0, 2),
}))
const provinces: SearchPlace[] = SPANISH_PROVINCES.map(({ id, es }) => ({ id, label: es, type: 'province', provinceCode: id }))
const places = [...provinces, ...municipalities]
const byId = new Map(places.map((place) => [place.id, place]))
const aliases = new Map(places.map((place) => [place.id, (place.type === 'municipality'
  ? municipalityAliases(catalog.municipalities[place.id as keyof typeof catalog.municipalities])
  : [place.label, ...(place.id === '38' ? ['Tenerife'] : place.id === '07' ? ['Baleares'] : [])]).map(normalizePlace)]))
export const getSearchPlace = (id: string) => byId.get(id)
export function resolveMunicipality(query: string, provinceCode?: string) {
  const term = normalizePlace(query)
  const matches = municipalities.filter((place) => (!provinceCode || place.provinceCode === provinceCode) && aliases.get(place.id)!.includes(term))
  return matches.length === 1 ? matches[0] : undefined
}
const recentKey = '112233:recent-locations:v1'
export function recentPlaces(): string[] {
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(recentKey) ?? '[]')
    return Array.isArray(stored) ? stored.filter((id): id is string => typeof id === 'string' && byId.has(id)).slice(0, 8) : []
  } catch { return [] }
}
export function rememberPlace(id: string) {
  if (!byId.has(id)) return
  try { localStorage.setItem(recentKey, JSON.stringify([id, ...recentPlaces().filter((value) => value !== id)].slice(0, 8))) } catch { /* Search works with storage disabled. */ }
}
export function locationSuggestions(query: string, recent = recentPlaces()) {
  const term = normalizePlace(query)
  const preferredProvince = byId.get(recent[0])?.provinceCode
  const rank = (place: SearchPlace) => {
    const names = aliases.get(place.id)!
    return [names.includes(term) ? 0 : 1, names.some((name) => name.startsWith(term)) ? 0 : 1,
      recent.includes(place.id) ? recent.indexOf(place.id) : 9, place.provinceCode === preferredProvince ? 0 : 1]
  }
  return places.filter((place) => !term ? place.type === 'province' || recent.includes(place.id)
    : aliases.get(place.id)!.some((name) => name.startsWith(term) || name.split(' ').some((word) => word.startsWith(term))) || place.id.startsWith(term))
    .sort((a, b) => {
      const ar = rank(a), br = rank(b)
      for (let i = 0; i < ar.length; i++) if (ar[i] !== br[i]) return ar[i] - br[i]
      return a.label.localeCompare(b.label, 'es') || a.id.localeCompare(b.id)
    })
}
export function listingInMunicipality(listing: Listing, id: string) {
  const place = byId.get(id)
  if (place?.type !== 'municipality') return false
  const province = listing.provinceCode ?? listing.postcode?.slice(0, 2)
  return (!province || province === place.provinceCode) && aliases.get(id)!.includes(normalizePlace(listing.city))
}
export const placeProvinceName = (place: SearchPlace) => getProvince(place.provinceCode)?.es ?? ''
