import { List, Map } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function ListMapSwitcher({ value, count, onChange, className = '' }: { value: 'list' | 'map'; count: number; onChange: (value: 'list' | 'map') => void; className?: string }) {
  return <div className={`list-map-switcher ${className}`} role="group" aria-label="Vista de resultados">
    <Button type="button" variant={value === 'list' ? 'default' : 'ghost'} aria-pressed={value === 'list'} onClick={() => onChange('list')}><List data-icon="inline-start" />Lista <span>{count}</span></Button>
    <Button type="button" variant={value === 'map' ? 'default' : 'ghost'} aria-pressed={value === 'map'} onClick={() => onChange('map')}><Map data-icon="inline-start" />Mapa</Button>
  </div>
}
