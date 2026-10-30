import { useEffect, useState } from 'react'
import { aiResultMap } from '@/api/ai-search'
import type { ListingMapMarker } from '@/api/listings'

// Only aliased in the explicit ai-synthetic-lab Vite mode. No fixture markers.
export function AIResultMap({ resultRef, intentHash }: { resultRef: string; intentHash: string }) {
  const [markers, setMarkers] = useState<ListingMapMarker[]>([])
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [zoom, setZoom] = useState(14)
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState('')
  const span = zoom === 14 ? .15 : .075
  const west = -16.8 + offset, south = 28.05
  useEffect(() => {
    const controller = new AbortController()
    setLoaded(false); setMarkers([]); setError(''); setSelected('')
    void aiResultMap(resultRef, { north: south + span, south, east: west + span, west, zoom }, controller.signal)
      .then(response => {
        if (response.intent_hash !== intentHash) throw new Error('Intent mismatch')
        if (!controller.signal.aborted) { setMarkers(response.map.items); setLoaded(true) }
      }).catch(() => { if (!controller.signal.aborted) setError('Не удалось прочитать verified map API') })
    return () => controller.abort()
  }, [resultRef, intentHash, zoom, span, west])
  return <section aria-label="Локальная координатная карта" data-i18n-exempt>
    <p>Локальная карта Adeje · координатная сетка, без внешних тайлов</p>
    <button type="button" onClick={() => setZoom(value => value === 14 ? 15 : 14)}>Масштаб {zoom}</button>{' '}
    <button type="button" onClick={() => setOffset(value => value === 0 ? .075 : 0)}>Сдвинуть область</button>
    <p role="status">{error || (loaded ? `Маркеров: ${markers.length}` : 'Чтение карты…')}</p>
    <svg viewBox="0 0 700 300" role="img" aria-label="Маркеры из verified map API" style={{ width: '100%', background: '#e8f2e1', border: '1px solid #657558' }}>
      {[0, 1, 2, 3, 4, 5].map(i => <g key={i} stroke="#bcccb5">
        <path d={`M${i * 140} 0V300 M0 ${i * 60}H700`} />
        <text x={i * 140 + 2} y="295" fill="#33412d" fontSize="10">{(west + i * span / 5).toFixed(3)}°</text>
      </g>)}
      {markers.map(marker => <g key={marker.id} data-listing-id={marker.id}
        transform={`translate(${(marker.longitude - west) / span * 700},${300 - (marker.latitude - south) / span * 300})`}
        role="button" tabIndex={0} aria-label={`Маркер ${marker.id}`} onClick={() => setSelected(marker.id)}
        onKeyDown={event => { if (event.key === 'Enter') setSelected(marker.id) }} style={{ cursor: 'pointer' }}>
        <circle r="17" fill={selected === marker.id ? '#c80079' : '#28653c'} />
        <text y="4" textAnchor="middle" fill="white" fontSize="10">{marker.type === 'listing' ? `${marker.price}€` : marker.count}</text>
      </g>)}
    </svg>
    {selected ? <p>Выбран ID: {selected}</p> : null}
  </section>
}
