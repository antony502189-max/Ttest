import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router'
import { useApp } from '@/contexts/app-context'
import {
  listingAccessProfileFromFilters,
  persistListingAccessProfile,
  readListingAccessProfile,
} from '@/lib/listing-access'
import { getCriticalRestrictions } from '@/lib/listings'
import type { Listing, TenantRequirement } from '@/types'

function expectedCapacity(requirement: TenantRequirement): Listing['roomCapacity'] | null {
  if (requirement === 'couple') return 2
  if (requirement === 'single-man' || requirement === 'single-woman' || requirement === 'single-person') return 1
  return null
}

export function PublishOccupancySync() {
  const { ownedListings, canManageListing, filters, updateListing } = useApp()
  const { pathname } = useLocation()
  const pending = useRef(new Set<string>())

  useEffect(() => {
    if (pathname !== '/buscar') return

    const profile = listingAccessProfileFromFilters(filters)
    if (profile.occupant === 'couple' || profile.occupant === 'family') {
      const visibleHomeProfile = readListingAccessProfile()
      persistListingAccessProfile({
        ...profile,
        occupant: visibleHomeProfile.occupant,
      })
      return
    }
    persistListingAccessProfile(profile)
  }, [filters, pathname])

  useEffect(() => {
    ownedListings.forEach((listing) => {
      // Shared rooms and bed-space listings have an explicit multi-person
      // capacity. Never collapse that capacity to 1/2 from the legacy primary
      // tenant requirement; doing so would destroy room-first occupancy data.
      if (listing.roomType === 'Habitación compartida' || listing.rentalUnit === 'bed') return
      const capacity = listing.tenantRequirement == null ? null : expectedCapacity(listing.tenantRequirement)
      if (!capacity || capacity === listing.roomCapacity || !canManageListing(listing) || pending.current.has(listing.id)) return

      const normalized: Listing = { ...listing, roomCapacity: capacity }
      normalized.restrictions = getCriticalRestrictions(normalized)
      pending.current.add(listing.id)
      void updateListing(listing.id, normalized).finally(() => {
        pending.current.delete(listing.id)
      })
    })
  }, [ownedListings, canManageListing, updateListing])

  return null
}
