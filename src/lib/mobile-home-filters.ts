import { defaultFilters } from '@/data/listings'
import { filtersForRentalMode } from '@/lib/price-filter-controls'
import { normalizeFilters } from '@/lib/search'
import type { Filters, RentalMode } from '@/types'

/** Home is a fresh-search boundary: keep only controls that are actually visible there. */
export function mobileHomeSearchFilters(filters: Filters, mode: RentalMode): Filters {
  const current = normalizeFilters(filters)
  let tenantRequirement: Filters['tenantRequirement'] = 'Cualquiera'
  let roomCapacity: Filters['roomCapacity'] = 'Cualquiera'

  if (current.tenantRequirement === 'single-man' || current.tenantRequirement === 'single-woman') {
    tenantRequirement = current.tenantRequirement
    roomCapacity = '1'
  } else if (current.tenantRequirement === 'single-person') {
    // Home '1 person' is capacity-only. A male-only/female-only room for one
    // person still matches this choice.
    roomCapacity = '1'
  } else if (current.tenantRequirement === 'couple' || current.roomCapacity === '2') {
    roomCapacity = '2'
  } else if (current.roomCapacity === '1') {
    roomCapacity = '1'
  }

  return filtersForRentalMode({
    ...defaultFilters,
    tenantRequirement,
    tenantRequirements: [],
    roomCapacity,
    children: current.children === 'Sí' ? 'Sí' : 'Cualquiera',
    pets: current.pets === 'Sí' ? 'Sí' : 'Cualquiera',
  }, mode)
}
