/** Display-only tariff labels. The server independently validates hours and calculates Stripe prices. */
export type PromotionHours = 12 | 24 | 72
export const TOP_PROMOTION_OFFERS = [
  { durationHours: 12 as const, amountCents: 99 },
  { durationHours: 24 as const, amountCents: 170 },
  { durationHours: 72 as const, amountCents: 450 },
]

export function promotionDurationLabel(hours: PromotionHours, language: string): string {
  if (language === 'ru') return hours === 72 ? '3 дня' : hours === 24 ? '24 часа' : '12 часов'
  if (language === 'en') return hours === 72 ? '3 days' : hours === 24 ? '24 hours' : '12 hours'
  return hours === 72 ? '3 días' : hours === 24 ? '24 horas' : '12 horas'
}

export function formatPromotionPrice(amountCents: number, locale: string): string {
  return new Intl.NumberFormat(locale, { style: 'currency', currency: 'EUR' }).format(amountCents / 100)
}
