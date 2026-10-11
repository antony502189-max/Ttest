/** The seventeen autonomous communities, without Ceuta and Melilla.
 * Geographic polygons from Code for America / click_that_hood, MIT, checked
 * into backend/app/spain_communities.json and shared between web and API.
 */
import geography from '../data/spain-communities.json'
import type { Listing } from '@/types'

export type Community = { id: string; es: string; en: string; ru: string; capitalEs: string; capitalEn: string; capitalRu: string; aliases: string[] }
export const SPANISH_COMMUNITIES: Community[] = [{"id":"01","es":"Andalucía","en":"Andalusia","ru":"Андалусия","capitalEs":"Sevilla","capitalEn":"Seville","capitalRu":"Севилья","aliases":["Sevilla","Málaga","Malaga","Granada","Córdoba","Cordoba","Cádiz","Cadiz","Huelva","Jaén","Jaen","Almería","Almeria","Marbella","Jerez"]},{"id":"02","es":"Aragón","en":"Aragon","ru":"Арагон","capitalEs":"Zaragoza","capitalEn":"Saragossa","capitalRu":"Сарагоса","aliases":["Zaragoza","Huesca","Teruel"]},{"id":"03","es":"Asturias","en":"Asturias","ru":"Астурия","capitalEs":"Oviedo","capitalEn":"Oviedo","capitalRu":"Овьедо","aliases":["Oviedo","Gijón","Gijon","Avilés","Aviles"]},{"id":"04","es":"Illes Balears","en":"Balearic Islands","ru":"Балеарские острова","capitalEs":"Palma","capitalEn":"Palma","capitalRu":"Пальма","aliases":["Baleares","Mallorca","Palma","Ibiza","Eivissa","Manacor","Mahón","Mahon","Menorca","Ciutadella"]},{"id":"05","es":"Canarias","en":"Canary Islands","ru":"Канарские острова","capitalEs":"Santa Cruz de Tenerife / Las Palmas","capitalEn":"Santa Cruz / Las Palmas","capitalRu":"Санта-Крус / Лас-Пальмас","aliases":["Canarias","Canary","Tenerife","Santa Cruz de Tenerife","Las Palmas","Las Palmas de Gran Canaria","Gran Canaria","Telde","Arona","Adeje","San Cristóbal de La Laguna","San Cristobal de La Laguna","Lanzarote","Arrecife","Fuerteventura","Puerto del Rosario","La Palma","El Hierro","La Gomera"]},{"id":"06","es":"Cantabria","en":"Cantabria","ru":"Кантабрия","capitalEs":"Santander","capitalEn":"Santander","capitalRu":"Сантандер","aliases":["Santander","Torrelavega"]},{"id":"07","es":"Castilla y León","en":"Castile and León","ru":"Кастилия-и-Леон","capitalEs":"Valladolid","capitalEn":"Valladolid","capitalRu":"Вальядолид","aliases":["Valladolid","León","Leon","Salamanca","Burgos","Ávila","Avila","Segovia","Soria","Palencia","Zamora","Ponferrada"]},{"id":"08","es":"Castilla-La Mancha","en":"Castile–La Mancha","ru":"Кастилия-Ла-Манча","capitalEs":"Toledo","capitalEn":"Toledo","capitalRu":"Толедо","aliases":["Toledo","Albacete","Cuenca","Ciudad Real","Guadalajara","Talavera de la Reina"]},{"id":"09","es":"Cataluña","en":"Catalonia","ru":"Каталония","capitalEs":"Barcelona","capitalEn":"Barcelona","capitalRu":"Барселона","aliases":["Catalunya","Cataluña","Barcelona","Girona","Gerona","Lleida","Lerida","Tarragona","Badalona","Sabadell","Terrassa","Mataró","Mataro","L'Hospitalet de Llobregat","Hospitalet","Reus"]},{"id":"10","es":"Comunitat Valenciana","en":"Valencian Community","ru":"Валенсия","capitalEs":"València","capitalEn":"Valencia","capitalRu":"Валенсия","aliases":["Comunidad Valenciana","Valencia","València","Alicante","Alacant","Castellón","Castello","Castellón de la Plana","Elche","Elx","Benidorm","Torrevieja","Gandía","Gandia","Dénia","Denia"]},{"id":"11","es":"Extremadura","en":"Extremadura","ru":"Эстремадура","capitalEs":"Mérida","capitalEn":"Merida","capitalRu":"Мерида","aliases":["Extremadura","Mérida","Merida","Badajoz","Cáceres","Caceres","Plasencia"]},{"id":"12","es":"Galicia","en":"Galicia","ru":"Галисия","capitalEs":"Santiago de Compostela","capitalEn":"Santiago de Compostela","capitalRu":"Сантьяго-де-Компостела","aliases":["Galicia","Santiago de Compostela","A Coruña","La Coruña","A Coruna","Vigo","Lugo","Ourense","Orense","Pontevedra","Ferrol"]},{"id":"13","es":"Comunidad de Madrid","en":"Community of Madrid","ru":"Мадрид","capitalEs":"Madrid","capitalEn":"Madrid","capitalRu":"Мадрид","aliases":["Madrid","Alcalá de Henares","Alcala de Henares","Getafe","Móstoles","Mostoles","Fuenlabrada","Leganés","Leganes","Alcorcón","Alcorcon","Pozuelo de Alarcón"]},{"id":"14","es":"Región de Murcia","en":"Region of Murcia","ru":"Мурсия","capitalEs":"Murcia","capitalEn":"Murcia","capitalRu":"Мурсия","aliases":["Murcia","Cartagena","Lorca","Molina de Segura","Águilas","Aguilas"]},{"id":"15","es":"Navarra","en":"Navarre","ru":"Наварра","capitalEs":"Pamplona","capitalEn":"Pamplona","capitalRu":"Памплона","aliases":["Navarra","Nafarroa","Pamplona","Iruña","Iruna","Tudela"]},{"id":"16","es":"País Vasco","en":"Basque Country","ru":"Страна Басков","capitalEs":"Vitoria-Gasteiz","capitalEn":"Vitoria-Gasteiz","capitalRu":"Витория-Гастейс","aliases":["Euskadi","Pais Vasco","País Vasco","Vitoria","Vitoria-Gasteiz","Bilbao","Bilbo","San Sebastián","San Sebastian","Donostia","Irun","Irún","Barakaldo","Getxo"]},{"id":"17","es":"La Rioja","en":"La Rioja","ru":"Ла-Риоха","capitalEs":"Logroño","capitalEn":"Logrono","capitalRu":"Логроньо","aliases":["Rioja","Logroño","Logrono","Calahorra","Haro"]}]
const polygonsById = new Map<string, number[][][][]>(geography.features.map((entry) => [entry.id, entry.polygons] as const))
const byId = new Map(SPANISH_COMMUNITIES.map((entry) => [entry.id, entry]))

export function getCommunity(id: string | null | undefined): Community | undefined {
  return id ? byId.get(id) : undefined
}
export function communityName(id: string | null | undefined, language: 'es' | 'en' | 'ru' = 'es'): string {
  const entry = getCommunity(id)
  return entry ? entry[language] : ({ es: 'España', en: 'Spain', ru: 'Вся Испания' })[language]
}
export function normalizeSpanishPlace(input: string): string {
  return input.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().replace(/[^a-z0-9а-яё ]/g, ' ').replace(/\s+/g, ' ').trim()
}
function terms(region: Community, extraCities: string[]): string[] {
  return [region.es, region.en, region.ru, region.capitalEs, region.capitalEn, region.capitalRu,
    ...region.aliases, ...extraCities].map(normalizeSpanishPlace)
}
export function communitySuggestions(input: string, dynamicCities: Record<string, string[]> = {}): Community[] {
  const search = normalizeSpanishPlace(input)
  if (!search) return SPANISH_COMMUNITIES
  return SPANISH_COMMUNITIES.filter((region) => terms(region, dynamicCities[region.id] ?? [])
    .some((name) => name.includes(search)))
}
export function resolveCommunityText(input: string, dynamicCities: Record<string, string[]> = {}): Community | undefined {
  const search = normalizeSpanishPlace(input)
  if (!search) return undefined
  // Exact region name first; then a city/capital alias. Other partial
  // queries remain suggestions until the visitor selects a visible row.
  return SPANISH_COMMUNITIES.find((region) => [region.es,region.en,region.ru].map(normalizeSpanishPlace).includes(search))
    ?? SPANISH_COMMUNITIES.find((region) => terms(region, dynamicCities[region.id] ?? []).includes(search))
}
function insideRing(lng: number, lat: number, ring: number[][]): boolean {
  let inside = false
  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index++) {
    const [x, y] = ring[index]
    const [px, py] = ring[previous]
    if ((y > lat) !== (py > lat) && lng < ((px - x) * (lat - y)) / (py - y) + x) inside = !inside
  }
  return inside
}
export function communityAtCoordinates(lat: number, lng: number): Community | undefined {
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return undefined
  return SPANISH_COMMUNITIES.find((region) => {
    const polygons = polygonsById.get(region.id)
    return polygons?.some((polygon) => insideRing(lng, lat, polygon[0] as number[][]))
  })
}
export function listingInCommunity(listing: Listing, id: string): boolean {
  if (!listing.coordinates || !Number.isFinite(listing.coordinates.lat) || !Number.isFinite(listing.coordinates.lng)) return false
  return communityAtCoordinates(listing.coordinates.lat, listing.coordinates.lng)?.id === id
}
function mercatorY(lat: number): number {
  const rad = Math.max(-85, Math.min(85, lat)) * Math.PI / 180
  return (1 - Math.log(Math.tan(Math.PI / 4 + rad / 2)) / Math.PI) / 2
}
function inverseMercatorY(y: number): number {
  return Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180 / Math.PI
}
export function communityMapCamera(id: string, width: number, height: number): { lat: number; lng: number; zoom: number } | undefined {
  const polygons = polygonsById.get(id)
  if (!polygons?.length) return undefined
  let north = -90, south = 90, east = -180, west = 180
  for (const polygon of polygons) for (const ring of polygon) for (const [lng, lat] of ring) {
    north = Math.max(north, lat); south = Math.min(south, lat)
    east = Math.max(east, lng); west = Math.min(west, lng)
  }
  const top = mercatorY(north), bottom = mercatorY(south)
  const centerY = (top + bottom) / 2
  const h = Math.max(0.0001, bottom - top)
  const w = Math.max(0.0001, (east - west) / 360)
  const zoom = Math.min(Math.log2(Math.max(240,width)*0.92/(256*w)), Math.log2(Math.max(240,height)*0.92/(256*h)))
  return { lat: inverseMercatorY(centerY), lng: (east + west)/2, zoom: Math.max(3, Math.min(16, zoom)) }
}
