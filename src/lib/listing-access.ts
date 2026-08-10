import type { Filters, TenantRequirement, YesNoAny } from '@/types'

export type HomeOccupantChoice = TenantRequirement | 'two-people' | 'with-children' | 'family' | null

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
  'two-people',
  'with-children',
  'family',
  'any',
])
const yesNoAnyValues = new Set<YesNoAny>(['Cualquiera', 'Sí', 'No'])

export const emptyListingAccessProfile: ListingAccessProfile = {
  occupant: null,
  pets: 'Cualquiera',
  smoking: 'Cualquiera',
}

let inMemoryProfile: ListingAccessProfile = { ...emptyListingAccessProfile }

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
    if (!raw) return { ...inMemoryProfile }
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
    inMemoryProfile = { occupant, pets, smoking }
    return { ...inMemoryProfile }
  } catch {
    return { ...inMemoryProfile }
  }
}

export function persistListingAccessProfile(profile: ListingAccessProfile) {
  inMemoryProfile = { ...profile }
  try {
    if (!hasListingAccessSelection(profile)) {
      localStorage.removeItem(STORAGE_KEY)
      return
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
  } catch {
    // The in-memory copy keeps navigation working when browser storage is unavailable.
  }
}

export function hasListingAccess() {
  return hasListingAccessSelection(readListingAccessProfile())
}

export function listingAccessProfileFromFilters(filters: Filters): ListingAccessProfile {
  let occupant: HomeOccupantChoice = null

  if (filters.children === 'Sí' && filters.tenantRequirement === 'Cualquiera') {
    occupant = 'with-children'
  } else if (filters.tenantRequirement === 'couple' && filters.children === 'Sí') {
    // Backward compatibility for profiles saved before the reference UI split
    // the generic children filter from the couple requirement.
    occupant = 'family'
  } else if (filters.roomCapacity === '2' && filters.tenantRequirement === 'Cualquiera') {
    occupant = 'two-people'
  } else if (filters.tenantRequirement !== 'Cualquiera') {
    occupant = filters.tenantRequirement
  }

  return {
    occupant,
    pets: filters.pets,
    smoking: filters.smoking,
  }
}

export function applyListingAccessProfile(filters: Filters, profile: ListingAccessProfile): Filters {
  let tenantRequirement: Filters['tenantRequirement'] = 'Cualquiera'
  let roomCapacity = 'Cualquiera'
  let children: YesNoAny = 'Cualquiera'

  switch (profile.occupant) {
    case 'single-man':
      tenantRequirement = 'single-man'
      roomCapacity = '1'
      break
    case 'single-woman':
      tenantRequirement = 'single-woman'
      roomCapacity = '1'
      break
    case 'single-person':
      tenantRequirement = 'single-person'
      roomCapacity = '1'
      break
    case 'couple':
      tenantRequirement = 'couple'
      roomCapacity = '2'
      break
    case 'two-people':
      roomCapacity = '2'
      break
    case 'with-children':
      children = 'Sí'
      break
    case 'family':
      // Legacy persisted value: retain its historical couple + children meaning.
      tenantRequirement = 'couple'
      roomCapacity = '2'
      children = 'Sí'
      break
    case 'any':
    case null:
      break
  }

  return {
    ...filters,
    tenantRequirement,
    tenantRequirements: [],
    roomCapacity,
    children,
    pets: profile.pets,
    smoking: profile.smoking,
  }
}
