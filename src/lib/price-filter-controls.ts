import type { Filters, RentalMode } from '@/types'
import { MAX_MONTHLY_RENT_EUR } from '@/lib/rental-policy'

export const TOURISM_PRICE_CEILING = 350
export const LONG_STAY_PRICE_CEILING = MAX_MONTHLY_RENT_EUR

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value))
}

/** Long-term price controls also normalize legacy saved ranges. */
export function priceControlValues(filters: Pick<Filters, 'minPrice' | 'maxPrice'>, _rentalMode: RentalMode) {
  const ceiling = LONG_STAY_PRICE_CEILING
  const unrestricted = filters.minPrice === 0 && filters.maxPrice === LONG_STAY_PRICE_CEILING
  const maximum = clamp(filters.maxPrice, 0, ceiling)
  const minimum = Math.min(clamp(filters.minPrice, 0, ceiling), maximum)
  return { minimum, maximum, ceiling, unrestricted }
}

/** Preserve valid price choices when normalizing a legacy rental mode. */
export function filtersForRentalMode(filters: Filters, rentalMode: RentalMode): Filters {
  const values = priceControlValues(filters, rentalMode)
  return { ...filters, minPrice: values.minimum, maxPrice: values.maximum }
}
