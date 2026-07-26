import { List, Map } from 'lucide-react'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { cn } from '@/lib/utils'
import '@/components/map/list-map-switcher-fix.css'

export function ListMapSwitcher({ value, count, onChange, className = '' }: { value: 'list' | 'map'; count: number; onChange: (value: 'list' | 'map') => void; className?: string }) {
  return <ToggleGroup type="single" value={value} onValueChange={(next) => { if (next === 'list' || next === 'map') onChange(next) }} variant="outline" spacing={0} className={cn('list-map-switcher', className)} aria-label="Vista de resultados">
    <ToggleGroupItem value="list" aria-label={`Mostrar lista de ${count} habitaciones`}><List data-icon="inline-start" />Lista <span>{count}</span></ToggleGroupItem>
    <ToggleGroupItem value="map" aria-label="Mostrar habitaciones en el mapa"><Map data-icon="inline-start" />Mapa</ToggleGroupItem>
  </ToggleGroup>
}
