import { defaultFilters } from '@/data/listings'
import type { RentalMode } from '@/types'

export type MobilePriceFilterState = {
  rentalMode: RentalMode | null
  minPrice: number
  maxPrice: number
}

export function mobileFiltersForRentalMode<T extends MobilePriceFilterState>(filters: T, mode: RentalMode): T {
  if (filters.rentalMode === mode) return filters
  if (mode !== 'holiday') return { ...filters, rentalMode: mode }
  if (filters.minPrice === defaultFilters.minPrice && filters.maxPrice === defaultFilters.maxPrice) {
    return { ...filters, rentalMode: mode }
  }
  return {
    ...filters,
    rentalMode: mode,
    minPrice: defaultFilters.minPrice,
    maxPrice: defaultFilters.maxPrice,
  }
}
