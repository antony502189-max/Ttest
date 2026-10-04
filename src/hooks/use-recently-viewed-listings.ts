import { useCallback, useEffect, useMemo, useState } from 'react'
import { getPublicCardsByIds } from '@/api/listings'
import { useApp } from '@/contexts/app-context'
import type { Listing } from '@/types'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'
const STORAGE_PREFIX = '112233:recently-viewed:v1'
const UPDATED_EVENT = 'recently-viewed:updated'
const MAX_RECENTLY_VIEWED = 20

function storageKey(scope: string) {
  return `${STORAGE_PREFIX}:${scope}`
}

function readIds(key: string) {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(key) ?? '[]')
    if (!Array.isArray(parsed)) return []
    return [...new Set(parsed.filter((value): value is string => typeof value === 'string' && Boolean(value.trim())))]
      .slice(0, MAX_RECENTLY_VIEWED)
  } catch {
    return []
  }
}

function notifyUpdated(key: string) {
  window.dispatchEvent(new CustomEvent(UPDATED_EVENT, { detail: { key } }))
}

export function recordRecentlyViewedListing(listingId: string, userId?: string | null) {
  if (!listingId) return
  const key = storageKey(userId ?? 'guest')
  const next = [listingId, ...readIds(key).filter((id) => id !== listingId)].slice(0, MAX_RECENTLY_VIEWED)
  try {
    localStorage.setItem(key, JSON.stringify(next))
    notifyUpdated(key)
  } catch {
    // Viewing a listing must keep working when browser storage is unavailable.
  }
}

export function useRecentlyViewedTracker() {
  const { currentUser } = useApp()
  return useCallback((listingId: string) => {
    recordRecentlyViewedListing(listingId, currentUser?.id)
  }, [currentUser?.id])
}

export function useRecentlyViewedListings(limit = MAX_RECENTLY_VIEWED) {
  const { currentUser, allListings } = useApp()
  const scope = currentUser?.id ?? 'guest'
  const key = useMemo(() => storageKey(scope), [scope])
  const [ids, setIds] = useState<string[]>(() => readIds(key))
  const [remote, setRemote] = useState<Listing[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const sync = () => setIds(readIds(key))
    sync()
    const onStorage = (event: StorageEvent) => {
      if (event.key === key) sync()
    }
    const onUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ key?: string }>).detail
      if (!detail?.key || detail.key === key) sync()
    }
    window.addEventListener('storage', onStorage)
    window.addEventListener(UPDATED_EVENT, onUpdated)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener(UPDATED_EVENT, onUpdated)
    }
  }, [key])

  const limitedIds = useMemo(() => ids.slice(0, Math.max(0, limit)), [ids, limit])
  const requestKey = limitedIds.join('|')

  useEffect(() => {
    if (mockMode) return
    const request = new AbortController()
    setError(false)
    if (!limitedIds.length) {
      setRemote([])
      setLoading(false)
      return () => request.abort()
    }
    setLoading(true)
    void getPublicCardsByIds(limitedIds, request.signal).then((items) => {
      if (request.signal.aborted) return
      const order = new Map(limitedIds.map((id, index) => [id, index]))
      setRemote([...items].sort((left, right) => (order.get(left.id) ?? Number.MAX_SAFE_INTEGER) - (order.get(right.id) ?? Number.MAX_SAFE_INTEGER)))
    }).catch(() => {
      if (!request.signal.aborted) setError(true)
    }).finally(() => {
      if (!request.signal.aborted) setLoading(false)
    })
    return () => request.abort()
    // requestKey is the stable request identity for the ordered ID list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestKey, retry])

  const listings = useMemo(() => {
    if (!mockMode) return remote
    const byId = new Map(allListings.map((listing) => [listing.id, listing]))
    return limitedIds.map((id) => byId.get(id)).filter((listing): listing is Listing => Boolean(listing))
  }, [allListings, limitedIds, remote])

  const mark = useCallback((listingId: string) => {
    recordRecentlyViewedListing(listingId, currentUser?.id)
  }, [currentUser?.id])

  const clear = useCallback(() => {
    try {
      localStorage.removeItem(key)
      setIds([])
      notifyUpdated(key)
    } catch {
      setIds([])
    }
  }, [key])

  return {
    ids: limitedIds,
    listings,
    loading,
    error,
    mark,
    clear,
    retry: () => setRetry((value) => value + 1),
  }
}
