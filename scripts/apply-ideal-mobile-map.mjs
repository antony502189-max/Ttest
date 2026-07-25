import fs from 'node:fs'

function patch(path, operations) {
  let source = fs.readFileSync(path, 'utf8')
  for (const [before, after, label] of operations) {
    if (!source.includes(before)) throw new Error(`${path}: missing patch anchor: ${label}`)
    source = source.replace(before, after)
  }
  fs.writeFileSync(path, source)
}

patch('src/components/mobile-app-v2.tsx', [
  [
    "import { cn } from '@/lib/utils'\n",
    "import { MobileMapListingsLayer } from '@/components/mobile-map-listings-layer'\nimport { cn } from '@/lib/utils'\n",
    'mobile map listings import',
  ],
  [
    "  const [drawing, setDrawing] = useState(mode === 'draw')\n  useEffect(() => { if (mode === 'draw' && mapStatus === 'ready' && polygon.length < 3) setDrawing(true) }, [mapStatus, mode, polygon.length])\n",
    "  const [drawing, setDrawing] = useState(false)\n",
    'remove automatic drawing activation',
  ],
  [
    "    <GoogleMapCanvas language={language} t={t} mapRef={mapRef} query={query} onStatus={setMapStatus} />\n    <FreehandAreaLayer",
    "    <GoogleMapCanvas language={language} t={t} mapRef={mapRef} query={query} onStatus={setMapStatus} />\n    <MobileMapListingsLayer mapRef={mapRef} mapReady={mapStatus === 'ready'} language={language} drawing={drawing} />\n    <FreehandAreaLayer",
    'mount listing markers on mobile map',
  ],
])

patch('src/components/layout.tsx', [
  ["import { MobileMapDrawingActivationFix } from '@/components/mobile-map-drawing-activation-fix'\n", '', 'remove drawing workaround import'],
  ['<MobileMapDrawingActivationFix /><MobileAppV2 />', '<MobileAppV2 />', 'remove drawing workaround mount'],
])

patch('src/components/mobile-search-results.tsx', [
  [
    "function formatPrice(listing: Listing, language: ResultsLanguage) {\n  const value = new Intl.NumberFormat(language === 'ru' ? 'ru-RU' : language === 'en' ? 'en-GB' : 'es-ES').format(listing.price)\n  const cadence = listing.cadence === 'noche' ? language === 'ru' ? 'ночь' : language === 'en' ? 'night' : 'noche' : language === 'ru' ? 'месяц' : language === 'en' ? 'month' : 'mes'\n  return `${value} € / ${cadence}`\n}\n",
    "function formatPrice(listing: Listing, language: ResultsLanguage) {\n  const value = new Intl.NumberFormat(language === 'ru' ? 'ru-RU' : language === 'en' ? 'en-GB' : 'es-ES').format(listing.price)\n  const cadence = listing.cadence === 'noche' ? language === 'ru' ? 'ночь' : language === 'en' ? 'night' : 'noche' : language === 'ru' ? 'месяц' : language === 'en' ? 'month' : 'mes'\n  return `${value} € / ${cadence}`\n}\n\nfunction capacityLabel(language: ResultsLanguage, count: number) {\n  if (language === 'ru') return `Комната для ${count} ${count === 1 ? 'человека' : 'человек'}`\n  if (language === 'en') return `Room for ${count} ${count === 1 ? 'person' : 'people'}`\n  return `Habitación para ${count} ${count === 1 ? 'persona' : 'personas'}`\n}\n",
    'capacity label helper',
  ],
  [
    "<div className=\"m2-result-card__badges\">{listing.restrictions.slice(0, 2).map((restriction) => <span key={restriction}>{restriction}</span>)}</div>",
    "<div className=\"m2-result-card__badges\">{Array.from(new Set([...listing.restrictions.slice(0, 2), capacityLabel(language, listing.roomCapacity)])).map((restriction) => <span key={restriction}>{restriction}</span>)}</div>",
    'prominent capacity requirement badge',
  ],
  [
    "  const [filters, setFilters] = useState<ResultsFilters>(() => createDefaultFilters())\n",
    "  const [filters, setFilters] = useState<ResultsFilters>(() => createDefaultFilters())\n  const [focusListingId, setFocusListingId] = useState('')\n",
    'focused listing state',
  ],
  [
    "      setLanguage(currentLanguage()); setPanel('results'); setOpen(true)\n",
    "      setFocusListingId(''); setLanguage(currentLanguage()); setPanel('results'); setOpen(true)\n",
    'clear focused listing for ordinary search',
  ],
  [
    "  }, [setRentalMode])\n\n  useEffect(() => {\n    if (!open) return\n",
    "  }, [setRentalMode])\n\n  useEffect(() => {\n    const openListing = (event: Event) => {\n      const listingId = (event as CustomEvent<{ listingId?: string }>).detail?.listingId ?? ''\n      const listing = allListings.find((item) => item.id === listingId)\n      if (!listing) return\n      setRentalMode(listing.rentalMode)\n      setFilters((current) => ({ ...current, rentalMode: listing.rentalMode }))\n      setFocusListingId(listingId)\n      setLanguage(currentLanguage())\n      setPanel('results')\n      setOpen(true)\n    }\n    window.addEventListener('112233:open-mobile-listing', openListing)\n    return () => window.removeEventListener('112233:open-mobile-listing', openListing)\n  }, [allListings, setRentalMode])\n\n  useEffect(() => {\n    if (!open || panel !== 'results' || !focusListingId) return\n    const frame = requestAnimationFrame(() => document.querySelector<HTMLElement>(`[data-listing-id=\"${CSS.escape(focusListingId)}\"]`)?.scrollIntoView({ block: 'start' }))\n    return () => cancelAnimationFrame(frame)\n  }, [focusListingId, open, panel])\n\n  useEffect(() => {\n    if (!open) return\n",
    'map marker to focused listing flow',
  ],
  [
    "  }), [favorites, filteredListings, order])\n\n  if (!open) return null\n",
    "  }), [favorites, filteredListings, order])\n  const orderedListings = useMemo(() => focusListingId ? [...listings].sort((left, right) => Number(right.id === focusListingId) - Number(left.id === focusListingId)) : listings, [focusListingId, listings])\n\n  if (!open) return null\n",
    'focused listing ordering',
  ],
  [
    "listings.length ? listings.map((listing, index) => <MobileResultCard",
    "orderedListings.length ? orderedListings.map((listing, index) => <MobileResultCard",
    'render focused listing first',
  ],
])

console.log('Ideal mobile map patch applied successfully.')
