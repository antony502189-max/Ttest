import { Check, Crosshair, Layers3, MapPin, Pencil, Search, Trash2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/contexts/i18n-context'
import { getAvailableTileProviders, type MapLayerId } from '@/lib/map/providers'
import { cn } from '@/lib/utils'

export function MapLayerSwitcher({ value, onChange }: { value: MapLayerId; onChange: (value: MapLayerId) => void }) {
  const providers = getAvailableTileProviders()
  if (providers.length < 2) return null
  return <div className="map-layer-switcher" role="group" aria-label="Capa del mapa">
    <Layers3 className="map-layer-switcher__icon" aria-hidden="true" />
    <div className="map-layer-switcher__options">
      {providers.map((provider) => <Button key={provider.id} type="button" variant="ghost" aria-pressed={value === provider.id} onClick={() => onChange(provider.id)}>{provider.label}</Button>)}
    </div>
    <Button
      type="button"
      className="map-layer-switcher__mobile-toggle"
      variant="outline"
      size="icon"
      aria-label={value === 'street' ? 'Mostrar mapa satélite' : 'Mostrar mapa estándar'}
      onClick={() => onChange(value === 'street' ? 'satellite' : 'street')}
    >
      <Layers3 aria-hidden="true" />
    </Button>
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
  onDeletePolygon: () => void
}

export function MapToolbar(props: MapToolbarProps) {
  const { language } = useI18n()
  const copy = {
    es: { tools: 'Herramientas del mapa', search: 'Buscar en esta zona', locate: 'Usar mi ubicación', add: 'Añadir punto', cancel: 'Cancelar', finish: 'Finalizar', redraw: 'Redibujar zona', remove: 'Eliminar zona', draw: 'Dibujar zona', hint: 'La zona dibujada sustituye a las zonas municipales seleccionadas' },
    en: { tools: 'Map tools', search: 'Search this area', locate: 'Use my location', add: 'Add point', cancel: 'Cancel', finish: 'Finish', redraw: 'Redraw area', remove: 'Delete area', draw: 'Draw area', hint: 'The drawn area replaces the selected municipal areas' },
    ru: { tools: 'Инструменты карты', search: 'Искать в этой области', locate: 'Моё местоположение', add: 'Добавить точку', cancel: 'Отмена', finish: 'Завершить', redraw: 'Нарисовать заново', remove: 'Удалить область', draw: 'Нарисовать область', hint: 'Нарисованная область заменит выбранные муниципальные зоны' },
  }[language]
  return <div className="map-toolbar" aria-label={copy.tools}>
    <Button className={cn('map-toolbar__search', props.boundsDirty && 'is-visible')} data-dirty={props.boundsDirty || undefined} onClick={props.onSearchBounds} disabled={!props.canSearchBounds} variant={props.boundsDirty ? 'default' : 'outline'}><Search data-icon="inline-start" />{copy.search}</Button>
    <Button className="map-toolbar__locate" variant="outline" size="icon" onClick={props.onLocate} aria-label={copy.locate}><Crosshair /></Button>
    {props.drawing ? <>
      <Button className="map-toolbar__drawing map-toolbar__add-point" variant="outline" onClick={props.onAddPoint}><MapPin data-icon="inline-start" />{copy.add}</Button>
      <Button className="map-toolbar__drawing map-toolbar__cancel" variant="outline" onClick={props.onCancelDrawing}><X data-icon="inline-start" />{copy.cancel}</Button>
      <Button className="map-toolbar__drawing map-toolbar__finish" disabled={props.pointCount < 3} onClick={props.onFinishDrawing}><Check data-icon="inline-start" />{copy.finish} ({props.pointCount})</Button>
    </> : props.hasPolygon ? <div className="map-toolbar__draw map-toolbar__polygon-group">
      <Button variant="outline" onClick={props.onStartDrawing}><Pencil data-icon="inline-start" />{copy.redraw}</Button>
      <Button variant="outline" size="icon" onClick={props.onDeletePolygon} aria-label={copy.remove}><Trash2 /></Button>
    </div> : <Button className="map-toolbar__draw" variant="outline" onClick={props.onStartDrawing} title={copy.hint}><Pencil data-icon="inline-start" />{copy.draw}</Button>}
  </div>
}
