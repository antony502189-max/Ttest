import type { Filters, RentalMode } from '@/types'

export const TOURISM_PRICE_CEILING = 350
export const LONG_STAY_PRICE_CEILING = 1200

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value))
}

/**
 * Keeps semantic search values separate from their mode-specific control
 * representation. The unrestricted 0–1200 range must stay intact so Tourism
 * searches do not acquire an implicit 350 EUR maximum.
 */
export function priceControlValues(filters: Pick<Filters, 'minPrice' | 'maxPrice'>, rentalMode: RentalMode) {
  const ceiling = rentalMode === 'holiday' ? TOURISM_PRICE_CEILING : LONG_STAY_PRICE_CEILING
  const unrestricted = filters.minPrice === 0 && filters.maxPrice === LONG_STAY_PRICE_CEILING
  const maximum = rentalMode === 'holiday' && unrestricted
    ? TOURISM_PRICE_CEILING
    : clamp(filters.maxPrice, 0, ceiling)
  const minimum = Math.min(clamp(filters.minPrice, 0, ceiling), maximum)
  return { minimum, maximum, ceiling, unrestricted }
}

/**
 * A Long Stay price constraint has different units and must never become an
 * implicit Tourism constraint. Restore the existing unrestricted sentinel
 * instead of converting it to the Tourism visual ceiling.
 */
export function filtersForRentalMode(filters: Filters, rentalMode: RentalMode): Filters {
  if (rentalMode !== 'holiday' || (filters.minPrice === 0 && filters.maxPrice === LONG_STAY_PRICE_CEILING)) return filters
  return { ...filters, minPrice: 0, maxPrice: LONG_STAY_PRICE_CEILING }
}
