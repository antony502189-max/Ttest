// Synchronized with the backend rental-policy API; parity is checked in CI.
export const MAX_MONTHLY_RENT_EUR = 1000
export const SUPPORTED_RENTAL_MODE = 'long' as const
export const RENTAL_POLICY_VERSION = 'long-eur-month-1000-v1'

export function rentalPriceError(language: string) {
  if (language.startsWith('ru')) return 'Месячная аренда с обязательными расходами не может превышать 1 000 €.'
  if (language.startsWith('en')) return 'Monthly rent including mandatory charges cannot exceed €1,000.'
  return 'El alquiler mensual no puede superar los 1.000 €.'
}

export function eligibleDraftPrice(draft: { rentalMode: string; monthlyPrice: number; billsIncluded: boolean; billsNote: string }) {
  const fees = draft.billsIncluded ? 0 : Number(draft.billsNote)
  return draft.rentalMode === SUPPORTED_RENTAL_MODE
    && Number.isInteger(draft.monthlyPrice) && draft.monthlyPrice > 0
    && Number.isInteger(fees) && fees >= 0
    && draft.monthlyPrice + fees <= MAX_MONTHLY_RENT_EUR
}
