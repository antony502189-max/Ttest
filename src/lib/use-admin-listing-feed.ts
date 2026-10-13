import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ADMIN_LISTING_PAGE_SIZE, getAdminHomepageHero, getAdminListingPage,
  type AdminListing, type HomepageHeroPromotion,
} from '@/api/admin'
import type { AdminRentalModeFilter } from '@/lib/admin-listings'

type Feed = {
  key: string
  rows: AdminListing[]
  cursor: AdminListing | null
  ready: boolean
  loading: boolean
  hasMore: boolean
  error: string
}

const emptyFeed = (key: string): Feed => ({ key, rows: [], cursor: null, ready: false, loading: false, hasMore: true, error: '' })

/** One active search, bounded initial rendering, and continuation on scroll. */
export function useAdminListingFeed(
  enabled: boolean,
  search: string,
  rentalMode: AdminRentalModeFilter,
  onHomepageHero: (value: HomepageHeroPromotion | null) => void,
) {
  const key = JSON.stringify([search, rentalMode])
  const [feed, setFeed] = useState(() => emptyFeed(key))
  const current = useRef(feed)
  const pending = useRef<AbortController | null>(null)
  const active = useRef(enabled)
  active.current = enabled
  const lastRow = useRef<HTMLElement | null>(null)
  const heroLoaded = useRef(false)
  const initialized = useRef(false)
  // An in-flight page must not undo moderation or resurrect a deleted row.
  const changes = useRef(new Map<string, AdminListing | null>())

  const publish = useCallback((next: Feed) => {
    current.current = next
    setFeed(next)
  }, [])

  const loadMore = useCallback(async () => {
    if (!active.current || current.current.key !== key || pending.current || !current.current.hasMore) return
    const controller = new AbortController()
    changes.current.clear()
    pending.current = controller
    publish({ ...current.current, loading: true, error: '' })
    try {
      const [page, hero] = await Promise.all([
        getAdminListingPage(search, rentalMode, current.current.cursor, controller.signal),
        heroLoaded.current ? Promise.resolve(undefined) : getAdminHomepageHero(controller.signal),
      ])
      if (controller.signal.aborted || current.current.key !== key) return
      if (hero !== undefined) {
        onHomepageHero(hero)
        heroLoaded.current = true
      }
      initialized.current = true
      const cursor = page.at(-1) ?? current.current.cursor
      if (page.length === ADMIN_LISTING_PAGE_SIZE && cursor?.id === current.current.cursor?.id) {
        throw new Error('La paginación de anuncios no avanzó.')
      }
      const seen = new Set(current.current.rows.map((row) => row.id))
      const appended: AdminListing[] = []
      for (const row of page) {
        const updated = changes.current.has(row.id) ? changes.current.get(row.id) : row
        if (!updated || seen.has(row.id)) continue
        seen.add(row.id)
        appended.push(updated)
      }
      publish({ ...current.current, rows: [...current.current.rows, ...appended], cursor,
        ready: true, loading: false, hasMore: page.length === ADMIN_LISTING_PAGE_SIZE, error: '' })
    } catch (error) {
      if (!controller.signal.aborted && current.current.key === key) {
        publish({ ...current.current, loading: false, error: error instanceof Error ? error.message : 'No se pudo completar la operación.' })
      }
    } finally {
      if (pending.current === controller) pending.current = null
    }
  }, [key, search, rentalMode, onHomepageHero, publish])

  useEffect(() => {
    if (!enabled) return
    if (current.current.key !== key) publish(emptyFeed(key))
    // Keep the search input mounted while replacing a query; wait briefly to
    // coalesce typing rather than sending every intermediate string.
    const timer = window.setTimeout(() => {
      if (!current.current.ready && !current.current.error) void loadMore()
    }, search ? 150 : 0)
    return () => {
      window.clearTimeout(timer)
      pending.current?.abort()
      pending.current = null
      if (current.current.loading) publish({ ...current.current, loading: false })
    }
  }, [enabled, key, loadMore, publish, search])

  useEffect(() => {
    if (!enabled || feed.key !== key || !feed.ready || feed.loading || !feed.hasMore || feed.error || !lastRow.current) return
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) void loadMore()
    }, { rootMargin: '600px' })
    observer.observe(lastRow.current)
    return () => observer.disconnect()
  }, [enabled, key, feed, loadMore])

  const observeLastRow = useCallback((element: HTMLElement | null) => { lastRow.current = element }, [])
  const replace = useCallback((row: AdminListing) => {
    if (pending.current) changes.current.set(row.id, row)
    publish({ ...current.current, rows: current.current.rows.map((item) => item.id === row.id ? row : item) })
  }, [publish])
  const remove = useCallback((id: string) => {
    if (pending.current) changes.current.set(id, null)
    publish({ ...current.current, rows: current.current.rows.filter((row) => row.id !== id) })
  }, [publish])
  const retry = useCallback(() => { void loadMore() }, [loadMore])
  const view = feed.key === key ? feed : emptyFeed(key)
  return { ...view, ready: initialized.current, loading: feed.key !== key || view.loading || (!view.ready && !view.error),
    observeLastRow, replace, remove, retry }
}
