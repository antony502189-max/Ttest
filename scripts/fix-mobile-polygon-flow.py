from pathlib import Path


def replace(path_name: str, old: str, new: str, label: str) -> None:
    path = Path(path_name)
    source = path.read_text(encoding='utf-8')
    if old not in source:
        raise SystemExit(f'{path_name}: missing anchor for {label}')
    path.write_text(source.replace(old, new, 1), encoding='utf-8')


replace(
    'src/components/mobile-app-v2.tsx',
    """  const navigateFromMap = (target: 'list' | 'filters' | 'area') => {\n    const params = new URLSearchParams(location.search)\n    params.delete('dibujar')\n    if (target !== 'area') params.delete('vista')\n    if (target === 'filters') params.set('panel', 'filtros')\n    else params.delete('panel')\n    navigate(`/buscar?${params.toString()}`)\n  }\n""",
    """  const navigateFromMap = (target: 'list' | 'filters' | 'area') => {\n    const params = new URLSearchParams(location.search)\n    params.delete('dibujar')\n    params.delete('vista')\n    params.delete('pagina')\n    if (target === 'filters') params.set('panel', 'filtros')\n    else params.delete('panel')\n    if (target === 'area' && mapPolygon.length >= 3) {\n      params.set('poligono', mapPolygon.map((point) => `${point.lat.toFixed(5)},${point.lng.toFixed(5)}`).join(';'))\n    }\n    navigate(`/buscar?${params.toString()}`)\n  }\n""",
    'search-area navigation',
)

replace(
    'src/contexts/app-context.tsx',
    "  const [mapPolygon, setMapPolygonState] = useState<MapPolygonPoint[]>(() => readJson<MapPolygonPoint[]>('112233:map-polygon:v1', []).data)\n",
    "  const [mapPolygon, setMapPolygonState] = useState<MapPolygonPoint[]>([])\n",
    'ephemeral polygon initial state',
)

replace(
    'src/contexts/app-context.tsx',
    "  useEffect(() => reportStorageFailure(persistJson('112233:map-polygon:v1', mapPolygon)), [mapPolygon, reportStorageFailure])\n",
    '',
    'remove polygon persistence',
)

app_path = Path('src/App.tsx')
app_source = app_path.read_text(encoding='utf-8')
anchor = """if (import.meta.env.VITE_E2E_BYPASS_ONBOARDING !== '1') {\n  try {\n    localStorage.removeItem('112233:mobile-onboarding:v1')\n  } catch {\n    // The onboarding still starts normally when browser storage is unavailable.\n  }\n}\n\n"""
cleanup = anchor + """try {\n  // A drawn map area belongs only to the current SPA session. A full page load\n  // starts a clean search while normal in-app navigation keeps the selection.\n  localStorage.removeItem('112233:map-polygon:v1')\n  const hash = window.location.hash\n  const queryIndex = hash.indexOf('?')\n  if (queryIndex >= 0) {\n    const route = hash.slice(0, queryIndex)\n    const params = new URLSearchParams(hash.slice(queryIndex + 1))\n    const hadTemporaryMapState = params.has('poligono') || params.has('dibujar')\n    params.delete('poligono')\n    params.delete('dibujar')\n    params.delete('pagina')\n    if (hadTemporaryMapState) {\n      const serialized = params.toString()\n      const nextHash = serialized ? `${route}?${serialized}` : route\n      window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}${nextHash}`)\n    }\n  }\n} catch {\n  // Temporary map state cleanup must not block application startup.\n}\n\n"""
if anchor not in app_source:
    raise SystemExit('src/App.tsx: missing startup anchor')
app_path.write_text(app_source.replace(anchor, cleanup, 1), encoding='utf-8')
