import { defaultFilters } from '@/data/listings'
import { applyListingAccessProfile, persistListingAccessProfile, readListingAccessProfile } from '@/lib/listing-access'
import { filtersToParams } from '@/lib/search'

const PENDING_KEY = '112233:mobile-home-search-pending:v1'

type HomeMode = 'long' | 'holiday'

// This flag intentionally lives only in memory. A pets value left in
// localStorage by the removed PR #155 home controls must not become active
// invisibly after a reload. We only preserve pets when the user has actually
// toggled the still-visible PR #154 "Con mascotas" option in the occupant
// sheet during the current app session.
let visibleHomePetsSelected = false

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
  return 'long'
}

function cleanHomeSearchParams(existing = new URLSearchParams(), mode = selectedHomeMode()) {
  // Home is a new search boundary. Only controls that are represented by the
  // restored Home UI are allowed to survive here; advanced result-panel and
  // removed PR #155 controls must not leak in.
  const accessProfile = readListingAccessProfile()
  const sanitizedAccessProfile = {
    ...accessProfile,
    // Pets still exists as a visible option inside the PR #154 occupant sheet,
    // so preserve it only after a real visible interaction in this app session.
    pets: visibleHomePetsSelected ? accessProfile.pets : defaultFilters.pets,
    // Smoking had no PR #154 Home control. Any persisted value is therefore
    // hidden state and must always be cleared at the Home search boundary.
    smoking: defaultFilters.smoking,
  }
  persistListingAccessProfile(sanitizedAccessProfile)

  const cleanFilters = applyListingAccessProfile({
    ...defaultFilters,
    areas: [],
    conditions: [],
    tenantRequirements: [],
    amenities: [],
  }, sanitizedAccessProfile)
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

  // CustomerFeedbackFixes replaces the original occupant sheet with these
  // visible controls. Observe the click before React/DOM synchronization so we
  // can distinguish an explicit PR #154 pets choice from stale PR #155 storage.
  const occupantOption = target.closest<HTMLButtonElement>('[data-m2-occupant-key]')
  if (occupantOption && document.querySelector('.m2-home')) {
    const key = occupantOption.dataset.m2OccupantKey
    if (key === 'pets') {
      visibleHomePetsSelected = occupantOption.getAttribute('aria-checked') !== 'true'
    } else if (key === 'unrestricted') {
      visibleHomePetsSelected = false
    }
  }

  const locationButton = target.closest('.m2-home .m2-select-row')
  if (locationButton) {
    safeSet(PENDING_KEY, selectedHomeMode())
    return
  }

  const searchButton = target.closest('.m2-home [data-testid="open-location"]')
  if (!searchButton) return

  event.preventDefault()
  event.stopPropagation()
  event.stopImmediatePropagation()
  safeRemove(PENDING_KEY)
  replaceHash('/buscar', cleanHomeSearchParams())
}

document.addEventListener('click', handleHomeInteraction, true)
window.addEventListener('hashchange', sanitizePendingLocationSearch)
