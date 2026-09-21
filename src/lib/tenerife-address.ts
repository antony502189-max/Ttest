import type { ListingDraft } from '@/types'

export const municipalities = [
  'Adeje','Arafo','Arico','Arona','Buenavista del Norte','Candelaria','El Rosario','El Sauzal','El Tanque','Fasnia','Garachico','Granadilla de Abona','Guía de Isora','Güímar','Icod de los Vinos','La Guancha','La Matanza de Acentejo','La Orotava','La Victoria de Acentejo','Los Realejos','Los Silos','Puerto de la Cruz','San Cristóbal de La Laguna','San Juan de la Rambla','San Miguel de Abona','Santa Cruz de Tenerife','Santa Úrsula','Santiago del Teide','Tacoronte','Tegueste','Vilaflor de Chasna',
] as const

export const municipalitySet = new Set<string>(municipalities)

const normalize = (value: string) => value
  .trim()
  .toLocaleLowerCase('es-ES')
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')

const normalizedMunicipalities = new Map(municipalities.map((value) => [normalize(value), value]))

export function municipalityAreaError(city: string, area: string) {
  const canonicalArea = normalizedMunicipalities.get(normalize(area))
  if (!canonicalArea || canonicalArea === city) return ''
  return `La zona “${area.trim()}” corresponde a otro municipio. Revisa Municipio o elige la dirección de las sugerencias.`
}

export function listingAddressFingerprint(
  value: Pick<ListingDraft, 'city' | 'area' | 'street' | 'postcode'>,
) {
  return [value.city, value.area, value.street, value.postcode]
    .map(normalize)
    .join('|')
}
