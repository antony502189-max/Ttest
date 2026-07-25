import fs from 'node:fs'

function read(path) {
  return fs.readFileSync(path, 'utf8')
}

function write(path, content) {
  fs.writeFileSync(path, content)
}

function replaceOnce(path, before, after, label) {
  const source = read(path)
  if (!source.includes(before)) throw new Error(`${path}: missing patch anchor: ${label}`)
  write(path, source.replace(before, after))
}

function replaceSection(path, startMarker, endMarker, replacementPath, label) {
  const source = read(path)
  const start = source.indexOf(startMarker)
  const end = source.indexOf(endMarker, start + startMarker.length)
  if (start < 0 || end < 0) throw new Error(`${path}: missing section anchors: ${label}`)
  write(path, source.slice(0, start) + read(replacementPath).trim() + '\n\n' + source.slice(end))
}

function replaceFrom(path, startMarker, replacementPath, label) {
  const source = read(path)
  const start = source.indexOf(startMarker)
  if (start < 0) throw new Error(`${path}: missing final section anchor: ${label}`)
  write(path, source.slice(0, start) + read(replacementPath).trim() + '\n')
}

write('src/components/mobile-map-listings-layer.tsx', read('.map-patch/mobile-map-listings-layer.tsx'))
write('tests/mobile-map-parity.spec.ts', read('.map-patch/mobile-map-parity.spec.ts'))

replaceOnce(
  'src/components/mobile-app-v2.tsx',
  "import { MobileMapListingsLayer } from '@/components/mobile-map-listings-layer'\nimport { cn } from '@/lib/utils'\n",
  "import { MobileMapListingsLayer, type MobileMapBounds } from '@/components/mobile-map-listings-layer'\nimport { useApp } from '@/contexts/app-context'\nimport { isInsideTenerife, resolveTenerifeLocation, TENERIFE_BOUNDS } from '@/lib/tenerife'\nimport { cn } from '@/lib/utils'\n",
  'mobile map integration imports',
)
replaceOnce('src/components/mobile-app-v2.tsx', "type SearchMode = 'vivienda' | 'turismo' | null\n", '', 'remove local rental mode type')
replaceOnce('src/components/mobile-app-v2.tsx', "const GENERAL_OCCUPANTS = new Set<OccupantOption>(['anyone', 'unrestricted'])\n", '', 'remove disconnected occupant set')
replaceOnce(
  'src/components/mobile-app-v2.tsx',
  "    locating: 'Buscando tu ubicación…', locationFound: 'Ubicación encontrada', locationDenied: 'No se pudo obtener tu ubicación', back: 'Volver', close: 'Cerrar', clear: 'Borrar búsqueda',",
  "    locating: 'Buscando tu ubicación…', locationFound: 'Ubicación encontrada', locationDenied: 'No se pudo obtener tu ubicación', searchThisArea: 'Buscar en esta zona', outsideTenerife: 'Tu ubicación está fuera de Tenerife', back: 'Volver', close: 'Cerrar', clear: 'Borrar búsqueda',",
  'Spanish map copy',
)
replaceOnce(
  'src/components/mobile-app-v2.tsx',
  "    mapError: 'Google Maps could not be loaded', locating: 'Finding your location…', locationFound: 'Location found', locationDenied: 'Your location could not be obtained',\n    back: 'Back', close: 'Close', clear: 'Clear search',",
  "    mapError: 'Google Maps could not be loaded', locating: 'Finding your location…', locationFound: 'Location found', locationDenied: 'Your location could not be obtained',\n    searchThisArea: 'Search this area', outsideTenerife: 'Your location is outside Tenerife', back: 'Back', close: 'Close', clear: 'Clear search',",
  'English map copy',
)
replaceOnce(
  'src/components/mobile-app-v2.tsx',
  "    locating: 'Определяем местоположение…', locationFound: 'Местоположение найдено', locationDenied: 'Не удалось определить местоположение', back: 'Назад', close: 'Закрыть', clear: 'Очистить поиск',",
  "    locating: 'Определяем местоположение…', locationFound: 'Местоположение найдено', locationDenied: 'Не удалось определить местоположение', searchThisArea: 'Искать в этой области', outsideTenerife: 'Ваше местоположение находится за пределами Тенерифе', back: 'Назад', close: 'Закрыть', clear: 'Очистить поиск',",
  'Russian map copy',
)
replaceSection('src/components/mobile-app-v2.tsx', 'function OccupantSelector', 'function HomeScreen', '.map-patch/occupant-selector.txt', 'connected occupant selector')
replaceSection('src/components/mobile-app-v2.tsx', 'function HomeScreen', 'function LocationScreen', '.map-patch/home-screen.txt', 'connected home mode')
replaceSection('src/components/mobile-app-v2.tsx', 'function LocationScreen', 'function GoogleMapCanvas', '.map-patch/location-screen.txt', 'connected location query')
replaceSection('src/components/mobile-app-v2.tsx', 'function GoogleMapCanvas', 'function captureMapInteractions', '.map-patch/google-map-canvas.txt', 'query-aware Google map')
replaceSection('src/components/mobile-app-v2.tsx', 'function MapScreen', 'function EmptyScreen', '.map-patch/map-screen.txt', 'fully connected map screen')
replaceFrom('src/components/mobile-app-v2.tsx', 'export function MobileAppV2()', '.map-patch/mobile-app-root.txt', 'mobile app global map state')

replaceOnce(
  'src/components/mobile-search-results.tsx',
  "import { useApp } from '@/contexts/app-context'\nimport type { Listing, RentalMode } from '@/types'\n",
  "import { useApp } from '@/contexts/app-context'\nimport { filterListings, pointInPolygon } from '@/lib/search'\nimport { listingMatchesTenerifeLocation, resolveTenerifeLocation } from '@/lib/tenerife'\nimport type { Listing, RentalMode } from '@/types'\n",
  'mobile result map filter imports',
)
replaceOnce(
  'src/components/mobile-search-results.tsx',
  "  const { allListings, discarded, discardListing, favorites, toggleFavorite, currentUser, setRentalMode } = useApp()",
  "  const { allListings, discarded, discardListing, favorites, toggleFavorite, currentUser, setRentalMode, rentalMode, filters: appFilters, query, mapPolygon } = useApp()",
  'mobile result global search state',
)
replaceOnce(
  'src/components/mobile-search-results.tsx',
  "      const mapList = Boolean(target.closest('.m2-map-toolbar')) && /listado|list|перечень/i.test(target.textContent ?? '')\n      if (!mainSearch && !mapList) return",
  "      if (!mainSearch) return",
  'remove map toolbar capture workaround',
)
replaceOnce(
  'src/components/mobile-search-results.tsx',
  "  useEffect(() => {\n    if (!open || panel !== 'results' || !focusListingId) return",
  read('.map-patch/results-open-effect.txt').trim() + "\n\n  useEffect(() => {\n    if (!open || panel !== 'results' || !focusListingId) return",
  'open actual map result panels',
)
replaceSection(
  'src/components/mobile-search-results.tsx',
  '  const availableListings = useMemo',
  '  const listings = useMemo',
  '.map-patch/results-filter-block.txt',
  'shared map and list filtering',
)
replaceOnce('src/components/mobile-search-results.tsx', '<small>{t.zone}</small>', '<small>{query || t.zone}</small>', 'show actual query in results')

const cssPath = 'src/mobile-map-ideal.css'
if (!read(cssPath).includes('.m2-map-search-area {')) {
  write(cssPath, read(cssPath).trimEnd() + '\n\n' + read('.map-patch/mobile-map-extra.css').trim() + '\n')
}

console.log('Mobile map parity patch applied successfully.')
