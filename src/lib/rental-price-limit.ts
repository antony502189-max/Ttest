export const MAX_LONG_TERM_RENT_EUR = 1000
export const longTermPriceError = 'El alquiler mensual no puede superar los 1.000 €.'

export function rentalPriceAllowed(mode: string, amount: number | null | undefined) {
  return mode !== 'long' || (typeof amount === 'number' && Number.isFinite(amount) && amount > 0 && amount <= MAX_LONG_TERM_RENT_EUR)
}
