import { useEffect, useRef } from 'react'
import { useApp } from '@/contexts/app-context'
import { listingAccessProfileFromFilters, persistListingAccessProfile } from '@/lib/listing-access'
import { getCriticalRestrictions } from '@/lib/listings'
import type { Listing, TenantRequirement } from '@/types'

function expectedCapacity(requirement: TenantRequirement): Listing['roomCapacity'] | null {
  if (requirement === 'couple') return 2
  if (requirement === 'single-man' || requirement === 'single-woman' || requirement === 'single-person') return 1
  return null
}

export function PublishOccupancySync() {
  const { allListings, canManageListing, filters, updateListing } = useApp()
  const pending = useRef(new Set<string>())

  useEffect(() => {
    const profile = listingAccessProfileFromFilters(filters)
    // The reference home chooser intentionally exposes broader "2 people" and
    // "with children" choices, not the advanced couple-only or
    // couple-plus-children combinations. Do not overwrite a visible home
    // selection with a profile that the home UI cannot faithfully represent.
    if (profile.occupant === 'couple' || profile.occupant === 'family') return
    persistListingAccessProfile(profile)
  }, [filters])

  useEffect(() => {
    allListings.forEach((listing) => {
      const capacity = listing.tenantRequirement == null ? null : expectedCapacity(listing.tenantRequirement)
      if (!capacity || capacity === listing.roomCapacity || !canManageListing(listing) || pending.current.has(listing.id)) return

      const normalized: Listing = { ...listing, roomCapacity: capacity }
      normalized.restrictions = getCriticalRestrictions(normalized)
      pending.current.add(listing.id)
      void updateListing(listing.id, normalized).finally(() => {
        pending.current.delete(listing.id)
      })
    })
  }, [allListings, canManageListing, updateListing])

  return null
}
