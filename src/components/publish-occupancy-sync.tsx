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
    persistListingAccessProfile(listingAccessProfileFromFilters(filters))
  }, [filters])

  useEffect(() => {
    allListings.forEach((listing) => {
      const capacity = expectedCapacity(listing.tenantRequirement)
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
