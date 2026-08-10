import { defaultFilters } from '@/data/listings'
import { applyListingAccessProfile, readListingAccessProfile } from '@/lib/listing-access'
import { filtersToParams } from '@/lib/search'

const PENDING_KEY = '112233:mobile-home-search-pending:v1'
const MODE_KEY = '112233:mobile-home-mode:v1'

type HomeMode = 'long' | 'holiday'

function safeGet(key: string) {
  try { return sessionStorage.getItem(key) } catch { return null }
}

function safeSet(key: string, value: string) {
  try { sessionStorage.setItem(key, value) } catch { /* In-memory DOM state still provides a safe default. */ }
}

function safeRemove(key: string) {
  try { sessionStorage.removeItem(key) } catch { /* Nothing to clear when storage is unavailable. */ }
}

function selectedHomeMode(): HomeMode {
  const buttons = Array.from(document.querySelectorAll<HTMLButtonElement>('.m2-home .m2-mode-switch > button'))
  const selectedIndex = buttons.findIndex((button) => button.getAttribute('aria-pressed') === 'true' || button.classList.contains('is-active'))
  if (selectedIndex === 1) return 'holiday'
  if (selectedIndex === 0) return 'long'
  return safeGet(MODE_KEY) === 'holiday' ? 'holiday' : 'long'
}

function cleanHomeSearchParams(existing = new URLSearchParams(), mode = selectedHomeMode()) {
  const cleanFilters = applyListingAccessProfile({
    ...defaultFilters,
    areas: [],
    conditions: [],
    tenantRequirements: [],
    amenities: [],
  }, readListingAccessProfile())
  const next = filtersToParams(cleanFilters)
  next.set('q', existing.get('q')?.trim() || 'Tenerife')
  next.set('alquiler', mode)

  // Spatial/navigation state belongs to the location flow and is safe to keep.
  for (const key of ['vista', 'dibujar', 'cerca', 'radio', 'lat', 'lng', 'poligono']) {
    const value = existing.get(key)
    if (value !== null) next.set(key, value)
  }
  return next
}

function currentHashRoute() {
  const hash = window.location.hash.replace(/^#/, '')
  const separator = hash.indexOf('?')
  return {
    pathname: separator >= 0 ? hash.slice(0, separator) : hash,
    params: new URLSearchParams(separator >= 0 ? hash.slice(separator + 1) : ''),
  }
}

function replaceHash(pathname: string, params: URLSearchParams) {
  const nextHash = `${pathname}?${params.toString()}`
  if (window.location.hash === `#${nextHash}`) return
  window.location.replace(`${window.location.pathname}${window.location.search}#${nextHash}`)
}

function sanitizePendingLocationSearch() {
  const pendingMode = safeGet(PENDING_KEY)
  if (pendingMode !== 'long' && pendingMode !== 'holiday') return
  const route = currentHashRoute()
  if (route.pathname !== '/buscar') return
  safeRemove(PENDING_KEY)
  replaceHash('/buscar', cleanHomeSearchParams(route.params, pendingMode))
}

function handleHomeInteraction(event: MouseEvent) {
  const target = event.target
  if (!(target instanceof Element)) return

  const modeButton = target.closest<HTMLButtonElement>('.m2-home .m2-mode-switch > button')
  if (modeButton) {
    const buttons = Array.from(modeButton.parentElement?.querySelectorAll<HTMLButtonElement>(':scope > button') ?? [])
    safeSet(MODE_KEY, buttons.indexOf(modeButton) === 1 ? 'holiday' : 'long')
    return
  }

  const locationButton = target.closest('.m2-home .m2-select-row')
  if (locationButton) {
    safeSet(PENDING_KEY, selectedHomeMode())
    return
  }

  const searchButton = target.closest('.m2-home [data-testid="open-location"]')
  if (!searchButton) return

  // A new home search must start from the home choices, not from stale
  // advanced filters left behind by a previous results session.
  event.preventDefault()
  event.stopPropagation()
  event.stopImmediatePropagation()
  const mode = selectedHomeMode()
  safeSet(MODE_KEY, mode)
  safeRemove(PENDING_KEY)
  replaceHash('/buscar', cleanHomeSearchParams(new URLSearchParams(), mode))
}

document.addEventListener('click', handleHomeInteraction, true)
window.addEventListener('hashchange', sanitizePendingLocationSearch)
