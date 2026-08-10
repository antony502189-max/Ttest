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
  const { allListings, canManageListing, filters, updateListing } = useApp()
  const { pathname } = useLocation()
  const pending = useRef(new Set<string>())

  useEffect(() => {
    // The persisted home chooser is the source of truth while the user is on
    // the home page. Only the advanced search route may project its filter
    // state back into that profile; otherwise an empty default filter set on
    // application mount would erase a valid (including migrated legacy)
    // occupant selection before HomeMandatorySearch can render it.
    if (pathname !== '/buscar') return

    const profile = listingAccessProfileFromFilters(filters)
    if (profile.occupant === 'couple' || profile.occupant === 'family') {
      // Advanced couple-only combinations do not have an exact option in the
      // simplified reference home chooser. Keep the currently visible home
      // occupant choice while still synchronizing independent pet/smoking
      // preferences so returning home never shows stale toggles.
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
