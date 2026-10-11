import { translateText, type Language } from '@/contexts/i18n-context'
import type { Listing } from '@/types'

function capacityLabel(language: Language, count: number | null): string {
  if (count == null) return translateText('Consultar con el anunciante', language)
  if (language === 'ru') return `Комната для ${count} ${count === 1 ? 'человека' : 'человек'}`
  if (language === 'en') return `Room for ${count} ${count === 1 ? 'person' : 'people'}`
  return `Habitación para ${count} ${count === 1 ? 'persona' : 'personas'}`
}

/**
 * Compare the actual fact rather than translated strings. Two distinct
 * Spanish descriptions of the same capacity translate to different Russian
 * phrases ("для 1 человека" / "для 1 чел."). Rendering both is wrong.
 */
function representsCapacity(value: string, capacity: number): boolean {
  const text = value.trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase()
  const match = text.match(/^(?:(?:habitacion|room|комната)\s+(?:para|for|для)\s+)?(\d+)\s+(?:personas?|people|persons?|человека?|человек|чел\.?|жильцов?)$/u)
  return match !== null && Number(match[1]) === capacity
}

/** Stable semantic badges for the same listing in all three UI languages. */
export function mobileResultBadges(listing: Pick<Listing, 'restrictions' | 'roomCapacity'>, language: Language): string[] {
  const capacity = listing.roomCapacity
  const source = listing.restrictions.slice(0, 2)
  const result: string[] = []
  const seen = new Set<string>()
  for (const raw of source) {
    const translated = translateText(raw, language).trim()
    if (!translated) continue
    if (capacity != null && (representsCapacity(raw, capacity) || representsCapacity(translated, capacity))) continue
    const key = translated.normalize('NFKC').toLocaleLowerCase(language === 'ru' ? 'ru' : 'es').replace(/\s+/g, ' ')
    if (seen.has(key)) continue
    seen.add(key)
    result.push(translated)
  }
  const capacityText = capacityLabel(language, capacity)
  if (!seen.has(capacityText.toLocaleLowerCase())) result.push(capacityText)
  return result
}
