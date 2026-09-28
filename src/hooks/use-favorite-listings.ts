import { useEffect, useMemo, useState } from 'react'
import { getPublicCardsByIds } from '@/api/listings'
import { useApp } from '@/contexts/app-context'
import type { Listing } from '@/types'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'

export function useFavoriteListings() {
  const { favorites, allListings } = useApp()
  const ids = useMemo(() => [...favorites].sort(), [favorites])
  const key = ids.join('|')
  const [remote, setRemote] = useState<Listing[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    if (mockMode) return
    const request = new AbortController()
    setLoading(Boolean(ids.length))
    setError(false)
    if (!ids.length) { setRemote([]); return }
    void getPublicCardsByIds(ids, request.signal).then((items) => {
      if (!request.signal.aborted) setRemote(items)
    }).catch(() => {
      if (!request.signal.aborted) setError(true)
    }).finally(() => {
      if (!request.signal.aborted) setLoading(false)
    })
    return () => request.abort()
    // The sorted ID key is the stable request identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, retry])

  const listings = mockMode ? allListings.filter((item) => favorites.has(item.id)) : remote.filter((item) => favorites.has(item.id))
  return { listings, loading, error, retry: () => setRetry((value) => value + 1) }
}
