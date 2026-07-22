import { Check, Crosshair, Heart, Layers3, MapPin, Pencil, Search, Trash2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getAvailableTileProviders, type MapLayerId } from '@/lib/map/providers'
import { cn } from '@/lib/utils'

export function MapLayerSwitcher({ value, onChange }: { value: MapLayerId; onChange: (value: MapLayerId) => void }) {
  const providers = getAvailableTileProviders()
  if (providers.length < 2) return null
  return <div className="map-layer-switcher" role="group" aria-label="Capa del mapa">
    <Layers3 aria-hidden="true" />
    {providers.map((provider) => <button key={provider.id} type="button" aria-pressed={value === provider.id} onClick={() => onChange(provider.id)}>{provider.label}</button>)}
  </div>
}

interface MapToolbarProps {
  boundsDirty: boolean
  canSearchBounds: boolean
  drawing: boolean
  pointCount: number
  hasPolygon: boolean
  onSearchBounds: () => void
  onLocate: () => void
  onStartDrawing: () => void
  onAddPoint: () => void
  onCancelDrawing: () => void
  onFinishDrawing: () => void
  onSavePolygon: () => void
  onDeletePolygon: () => void
}

export function MapToolbar(props: MapToolbarProps) {
  return <div className="map-toolbar" aria-label="Herramientas del mapa">
    <Button className={cn('map-toolbar__search', props.boundsDirty && 'is-visible')} data-dirty={props.boundsDirty || undefined} onClick={props.onSearchBounds} disabled={!props.canSearchBounds} variant={props.boundsDirty ? 'default' : 'outline'}><Search data-icon="inline-start" />Buscar en esta zona</Button>
    <Button variant="outline" size="icon" onClick={props.onLocate} aria-label="Usar mi ubicación"><Crosshair /></Button>
    {props.drawing ? <>
      <Button variant="outline" onClick={props.onAddPoint}><MapPin data-icon="inline-start" />Añadir punto</Button>
      <Button variant="outline" onClick={props.onCancelDrawing}><X data-icon="inline-start" />Cancelar</Button>
      <Button disabled={props.pointCount < 3} onClick={props.onFinishDrawing}><Check data-icon="inline-start" />Finalizar ({props.pointCount})</Button>
    </> : props.hasPolygon ? <>
      <Button variant="outline" onClick={props.onSavePolygon}><Heart data-icon="inline-start" />Guardar zona</Button>
      <Button variant="outline" onClick={props.onDeletePolygon}><Trash2 data-icon="inline-start" />Eliminar zona</Button>
    </> : <Button variant="outline" onClick={props.onStartDrawing} title="La zona dibujada sustituye a las zonas municipales seleccionadas"><Pencil data-icon="inline-start" />Dibujar zona</Button>}
  </div>
}
