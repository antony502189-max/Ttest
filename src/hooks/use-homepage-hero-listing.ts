import { useEffect, useState } from 'react'
import { getHomepageHeroListing } from '@/api/listings'
import type { Listing } from '@/types'

export function useHomepageHeroListing() {
  const [listing, setListing] = useState<Listing | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const next = await getHomepageHeroListing()
        if (!cancelled) setListing(next)
      } catch {
        if (!cancelled) setListing(null)
      }
    }
    const refresh = () => { void load() }
    void load()
    const expiryPoll = window.setInterval(load, 60_000)
    window.addEventListener('catalog:refresh', refresh)
    return () => {
      cancelled = true
      window.clearInterval(expiryPoll)
      window.removeEventListener('catalog:refresh', refresh)
    }
  }, [])

  return listing
}
