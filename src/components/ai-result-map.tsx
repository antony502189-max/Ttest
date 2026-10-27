import { useMemo, useState } from 'react'
import { aiResultMap } from '@/api/ai-search'
import { MapView, type MapBounds } from '@/components/marketplace'
import type { MappedListing } from '@/types'

const EMPTY_ITEMS: MappedListing[] = []

export function AIResultMap({ resultRef, intentHash }: { resultRef: string; intentHash: string }) {
  const [selected, setSelected] = useState('')
  const source = useMemo(() => ({
    key: `${resultRef}:${intentHash}`,
    async load(viewport: MapBounds & { zoom: number }, signal: AbortSignal) {
      const response = await aiResultMap(resultRef, viewport, signal)
      if (response.intent_hash !== intentHash) throw new Error('AI_MAP_INTENT_MISMATCH')
      return response.map.items
    },
  }), [resultRef, intentHash])
  return <div className="ai-result-map"><MapView items={EMPTY_ITEMS} serverSource={source} independentSearch
    selectedId={selected} onSelect={setSelected} /></div>
}
