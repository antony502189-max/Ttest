import type { Language } from '@/contexts/i18n-context'
import type { BedType } from '@/types'

/** API values remain stable; this is the single customer-facing label map. */
const labels: Record<Language, Record<BedType, string>> = {
  es: { single: 'Cama individual', double: 'Cama doble', bunk: 'Litera' },
  ru: { single: 'Односпальная кровать', double: 'Двуспальная кровать', bunk: 'Двухъярусная кровать' },
  en: { single: 'Single bed', double: 'Double bed', bunk: 'Bunk bed' },
}

export function bedTypeLabel(language: Language, bedType: BedType): string {
  return labels[language][bedType]
}

export function bedTypeOptionLabel(language: Language, bedType: BedType): string {
  const places = bedType === 'single' ? 1 : 2
  if (language === 'es') {
    const label = bedType === 'single' ? 'individual' : bedType === 'double' ? 'doble' : 'litera'
    return `${places} ${places === 1 ? 'plaza' : 'plazas'} / ${label}`
  }
  const prefix = language === 'ru'
    ? `${places} ${places === 1 ? 'место' : 'места'}`
    : language === 'en'
      ? `${places} ${places === 1 ? 'bed space' : 'bed spaces'}`
  return `${prefix} / ${bedTypeLabel(language, bedType)}`
}
