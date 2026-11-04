import { useEffect, useMemo, useRef, useState } from 'react'
import { aiResultMap } from '@/api/ai-search'
import { getPublicListing } from '@/api/listings'
import { MapView, type MapBounds } from '@/components/marketplace'
import { useI18n } from '@/contexts/i18n-context'
import type { MappedListing } from '@/types'

const EMPTY_ITEMS: MappedListing[] = []

export function AIResultMap({ resultRef, intentHash, refreshVersion, initialListingId }: {
  resultRef: string; intentHash: string; refreshVersion: number; initialListingId?: string
}) {
  const { t } = useI18n()
  const [selected, setSelected] = useState('')
  const initialListing = useRef(initialListingId)
  const [initialCamera, setInitialCamera] = useState<{ lat: number; lng: number; zoom: number } | null>()
  // Card payloads intentionally omit coordinates. Read the existing public
  // detail for the first verified card; use only its approximate coordinates.
  // A new result remounts this component; same-ref refresh never moves it.
  useEffect(() => {
    if (!initialListing.current) { setInitialCamera(null); return }
    const controller = new AbortController()
    void getPublicListing(initialListing.current, controller.signal).then(listing => {
      if (controller.signal.aborted) return
      const point = listing.coordinates
      setInitialCamera(point && Number.isFinite(point.lat) && Number.isFinite(point.lng)
        && Math.abs(point.lat) <= 85 && Math.abs(point.lng) <= 180 ? { lat: point.lat, lng: point.lng, zoom: 12 } : null)
    }).catch(() => { if (!controller.signal.aborted) setInitialCamera(null) })
    return () => controller.abort()
  }, [])
  const source = useMemo(() => ({
    key: `${resultRef}:${intentHash}:${refreshVersion}`,
    async load(viewport: MapBounds & { zoom: number }, signal: AbortSignal) {
      const response = await aiResultMap(resultRef, viewport, signal)
      if (response.intent_hash !== intentHash) throw new Error('AI_MAP_INTENT_MISMATCH')
      return response.map.items
    },
  }), [resultRef, intentHash, refreshVersion])
  return <div className="ai-result-map">{initialCamera === undefined ? <p role="status">{t('Cargando…')}</p> : <MapView items={EMPTY_ITEMS} serverSource={source} independentSearch
    initialCamera={initialCamera ?? undefined}
    selectedId={selected} onSelect={setSelected} />}</div>
}
