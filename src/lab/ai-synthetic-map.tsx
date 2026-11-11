import { useEffect, useRef, useState } from 'react'
import { aiResultMap } from '@/api/ai-search'
import type { ListingMapMarker } from '@/api/listings'

// Coordinate renderer for the lab and bounded real-data beta. No fixture markers.
export function AIResultMap({ resultRef, intentHash, refreshVersion, center, total }: {
  resultRef: string; intentHash: string; refreshVersion: number; center?: { lat: number; lng: number }; total: number
}) {
  const [markers, setMarkers] = useState<ListingMapMarker[]>([])
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [zoom, setZoom] = useState(14)
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState('')
  const [retryVersion, setRetryVersion] = useState(0)
  const [camera, setCamera] = useState(center ?? { lat: 28.125, lng: -16.725 })
  const manualCamera = useRef(false)
  const centerLat = center?.lat, centerLng = center?.lng
  useEffect(() => {
    if (!manualCamera.current && centerLat !== undefined && centerLng !== undefined) {
      setCamera({ lat: centerLat, lng: centerLng }); setOffset(0)
    }
  }, [centerLat, centerLng])
  const span = zoom === 14 ? .15 : .075
  const west = camera.lng - span / 2 + offset, south = camera.lat - span / 2
  useEffect(() => {
    const controller = new AbortController()
    setLoaded(false); setMarkers([]); setError(''); setSelected('')
    void aiResultMap(resultRef, { north: south + span, south, east: west + span, west, zoom }, controller.signal)
      .then(response => {
        if (response.intent_hash !== intentHash) throw new Error('Intent mismatch')
        if (!controller.signal.aborted) { setMarkers(response.map.items); setLoaded(true) }
      }).catch(() => { if (!controller.signal.aborted) setError('Не удалось прочитать verified map API') })
    return () => controller.abort()
  }, [resultRef, intentHash, refreshVersion, retryVersion, zoom, span, west, south])
  return <section aria-label="Локальная координатная карта" data-i18n-exempt>
    <p>Локальная координатная сетка, без внешних тайлов</p>
    <button type="button" style={{ padding: '.4rem .7rem', border: '1px solid #657558', borderRadius: '.5rem' }}
      onClick={() => { manualCamera.current = true; setZoom(value => value === 14 ? 15 : 14) }}>Масштаб {zoom}</button>{' '}
    <button type="button" style={{ padding: '.4rem .7rem', border: '1px solid #657558', borderRadius: '.5rem' }}
      onClick={() => { manualCamera.current = true; setOffset(value => value === 0 ? span / 4 : 0) }}>Сдвинуть область</button>
    <p role="status">{error || (loaded ? `Маркеров: ${markers.length}` : 'Чтение карты…')}</p>
    {error ? <button type="button" onClick={() => setRetryVersion(value => value + 1)}>Повторить загрузку карты</button> : null}
    {loaded && !markers.length && total > 0 ? <p role="status">В этой области нет актуальных маркеров. Объявления могли измениться или находятся в другой области.
      {center ? <button type="button" onClick={() => { manualCamera.current = false; setCamera(center); setOffset(0) }}>Показать область результатов</button> : null}
    </p> : null}
    <svg viewBox="0 0 700 300" role="img" aria-label="Маркеры из verified map API" style={{ width: '100%', background: '#e8f2e1', border: '1px solid #657558' }}>
      {[0, 1, 2, 3, 4, 5].map(i => <g key={i} stroke="#bcccb5">
        <path d={`M${i * 140} 0V300 M0 ${i * 60}H700`} />
        <text x={i * 140 + 2} y="295" fill="#33412d" fontSize="10">{(west + i * span / 5).toFixed(3)}°</text>
        <text x="2" y={i * 60 + 12} fill="#33412d" fontSize="10">{(south + span - i * span / 5).toFixed(3)}°</text>
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
