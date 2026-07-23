import type { Filters, TenantRequirement, YesNoAny } from '@/types'

export type HomeOccupantChoice = TenantRequirement | 'family' | null

export interface ListingAccessProfile {
  occupant: HomeOccupantChoice
  pets: YesNoAny
  smoking: YesNoAny
}

const STORAGE_KEY = '112233:listing-access-profile:v1'
const occupantValues = new Set<HomeOccupantChoice>([
  null,
  'single-man',
  'single-woman',
  'single-person',
  'couple',
  'family',
  'any',
])
const yesNoAnyValues = new Set<YesNoAny>(['Cualquiera', 'Sí', 'No'])

export const emptyListingAccessProfile: ListingAccessProfile = {
  occupant: null,
  pets: 'Cualquiera',
  smoking: 'Cualquiera',
}

export function hasListingAccessSelection(profile: ListingAccessProfile) {
  return Boolean(
    profile.occupant ||
    profile.pets !== 'Cualquiera' ||
    profile.smoking !== 'Cualquiera',
  )
}

export function readListingAccessProfile(): ListingAccessProfile {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...emptyListingAccessProfile }
    const parsed = JSON.parse(raw) as Partial<ListingAccessProfile>
    const occupant = occupantValues.has(parsed.occupant as HomeOccupantChoice)
      ? parsed.occupant as HomeOccupantChoice
      : null
    const pets = yesNoAnyValues.has(parsed.pets as YesNoAny)
      ? parsed.pets as YesNoAny
      : 'Cualquiera'
    const smoking = yesNoAnyValues.has(parsed.smoking as YesNoAny)
      ? parsed.smoking as YesNoAny
      : 'Cualquiera'
    return { occupant, pets, smoking }
  } catch {
    return { ...emptyListingAccessProfile }
  }
}

export function persistListingAccessProfile(profile: ListingAccessProfile) {
  try {
    if (!hasListingAccessSelection(profile)) {
      localStorage.removeItem(STORAGE_KEY)
      return
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
  } catch {
    // Search remains usable for the current render even when storage is unavailable.
  }
}

export function hasListingAccess() {
  return hasListingAccessSelection(readListingAccessProfile())
}

export function listingAccessProfileFromFilters(filters: Filters): ListingAccessProfile {
  const occupant: HomeOccupantChoice =
    filters.tenantRequirement === 'couple' && filters.children === 'Sí'
      ? 'family'
      : filters.tenantRequirement === 'Cualquiera'
        ? null
        : filters.tenantRequirement

  return {
    occupant,
    pets: filters.pets,
    smoking: filters.smoking,
  }
}

export function applyListingAccessProfile(filters: Filters, profile: ListingAccessProfile): Filters {
  const family = profile.occupant === 'family'
  const tenantRequirement = family
    ? 'couple'
    : profile.occupant ?? 'Cualquiera'

  return {
    ...filters,
    tenantRequirement,
    children: family ? 'Sí' : 'Cualquiera',
    pets: profile.pets,
    smoking: profile.smoking,
  }
}
