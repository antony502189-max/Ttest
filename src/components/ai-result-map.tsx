import { useMemo, useState } from 'react'
import { aiResultMap } from '@/api/ai-search'
import { MapView, type MapBounds } from '@/components/marketplace'
import { useI18n } from '@/contexts/i18n-context'
import type { MappedListing } from '@/types'
import type { AIAuthority } from '@/api/client'

const EMPTY_ITEMS: MappedListing[] = []

export function AIResultMap({ resultRef, intentHash, refreshVersion, center, total, authority }: {
  resultRef: string; intentHash: string; refreshVersion: number; center?: { lat: number; lng: number }; total: number; authority?: AIAuthority
}) {
  const { t } = useI18n()
  const [selected, setSelected] = useState('')
  const [emptyViewport, setEmptyViewport] = useState(false)
  const [cameraRequest, setCameraRequest] = useState(0)
  const source = useMemo(() => ({
    key: `${authority ?? 'default'}:${resultRef}:${intentHash}:${refreshVersion}`,
    async load(viewport: MapBounds & { zoom: number }, signal: AbortSignal) {
      const response = await aiResultMap(resultRef, viewport, signal, authority)
      if (response.intent_hash !== intentHash) throw new Error('AI_MAP_INTENT_MISMATCH')
      if (!signal.aborted) setEmptyViewport(response.map.items.length === 0)
      return response.map.items
    },
  }), [resultRef, intentHash, refreshVersion, authority])
  const camera = center ? { ...center, zoom: 12 } : undefined
  return <div className="ai-result-map">
    {emptyViewport && total > 0 ? <p role="status">{t('No hay marcadores actuales en esta zona. Puede haber resultados en otras zonas o cambios en los anuncios. Actualiza la lista.')}
      {center ? <button type="button" onClick={() => setCameraRequest(value => value + 1)}>{t('Mostrar el área de resultados')}</button> : null}
    </p> : null}
    <MapView items={EMPTY_ITEMS} serverSource={source} independentSearch initialCamera={camera}
      cameraTarget={camera} cameraRequestVersion={cameraRequest} selectedId={selected} onSelect={setSelected} />
  </div>
}
