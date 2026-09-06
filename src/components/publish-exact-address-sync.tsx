import { useEffect } from 'react'
import { useI18n } from '@/contexts/i18n-context'
import { googleMapsTestSdkEnabled, loadGoogleMaps } from '@/lib/google-maps/loader'
import { TENERIFE_BOUNDS, isInsideTenerife, normalizeTenerifeText } from '@/lib/tenerife'
import { createRequestVersionGate } from '@/lib/google-maps/address'
import type { Coordinates } from '@/types'
import '@/publication-exact-address-map.css'

declare global {
  interface Window {
    __112233TestAddressGeocode?: (query: string) => Promise<google.maps.GeocoderResult[]>
  }
}

type PlaceAutocompleteWithValue = google.maps.places.PlaceAutocompleteElement & { value?: string }
type SelectedLocationDetail = { coordinates?: Coordinates; zoom?: number; clearDetectedAddress?: boolean }

const EXACT_ADDRESS_ZOOM = 18
const STREET_ADDRESS_ZOOM = 16
const ADDRESS_DEBOUNCE_MS = 650

function component(result: google.maps.GeocoderResult, type: string) {
  return result.address_components?.find((item) => item.types.includes(type))?.long_name?.trim() ?? ''
}

function normalizeHouseNumber(value: string) {
  return value.trim().toLocaleLowerCase().replace(/[\s-]+/g, '')
}

function normalizeRoute(value: string) {
  return normalizeTenerifeText(value)
    .replace(/[.,ºª]/g, ' ')
    .replace(/^(calle|c|avenida|av|avda|carretera|ctra|camino|paseo|plaza|urbanizacion)\s+/, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function requestedHouseNumber(street: string) {
  return [...street.matchAll(/\b\d+[A-Za-z]?\b/g)].at(-1)?.[0] ?? ''
}

function requestedRoute(street: string) {
  const number = requestedHouseNumber(street)
  if (!number) return street.trim()
  const escaped = number.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return street.replace(new RegExp(`\\s*,?\\s*${escaped}\\s*$`, 'i'), '').trim()
}

function resultCoordinates(result: google.maps.GeocoderResult): Coordinates | null {
  const location = result.geometry?.location
  if (!location) return null
  const lat = typeof location.lat === 'function' ? location.lat() : Number((location as unknown as { lat?: number }).lat)
  const lng = typeof location.lng === 'function' ? location.lng() : Number((location as unknown as { lng?: number }).lng)
  return Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : null
}

function resultMatchesQuery(result: google.maps.GeocoderResult, street: string, postcode: string, city: string) {
  const coordinates = resultCoordinates(result)
  if (!coordinates || !isInsideTenerife(coordinates)) return false

  const resolvedPostcode = component(result, 'postal_code')
  if (/^\d{5}$/.test(postcode) && resolvedPostcode !== postcode) return false

  const resolvedMunicipality = component(result, 'administrative_area_level_3')
    || component(result, 'administrative_area_level_4')
  if (resolvedMunicipality && normalizeTenerifeText(resolvedMunicipality) !== normalizeTenerifeText(city)) return false

  const route = component(result, 'route')
  if (!route) return false
  const wantedRoute = requestedRoute(street)
  if (wantedRoute && normalizeRoute(route) !== normalizeRoute(wantedRoute)) return false

  const resultTypes = result.types ?? []
  const streetLike = resultTypes.some((type) => ['street_address', 'route', 'premise', 'subpremise'].includes(type))
  if (!streetLike) return false

  const wantedNumber = requestedHouseNumber(street)
  if (wantedNumber) {
    const resolvedNumber = component(result, 'street_number')
    if (!resolvedNumber || normalizeHouseNumber(resolvedNumber) !== normalizeHouseNumber(wantedNumber)) return false
  }
  return true
}

export function PublishExactAddressSync() {
  const { language } = useI18n()
  const notFoundMessage = language === 'ru'
    ? 'Не удалось точно определить этот адрес. Проверьте улицу, номер и индекс или выберите подсказку Google.'
    : language === 'en'
      ? 'This address could not be located precisely. Check the street, number and postcode or choose a Google suggestion.'
      : 'No se pudo ubicar esta dirección con precisión. Revisa calle, número y código postal o elige una sugerencia de Google.'

  useEffect(() => {
    let cancelled = false
    let timer: number | undefined
    let rawAutocompleteStreet = ''
    const gate = createRequestVersionGate()
    const cleanups = new Map<Element, () => void>()

    const cancelPending = () => {
      gate.next()
      if (timer !== undefined) window.clearTimeout(timer)
      timer = undefined
    }

    const dispatchAddressPoint = (coordinates: Coordinates, zoom: number, clearDetectedAddress = true) => {
      window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: '' } }))
      window.dispatchEvent(new CustomEvent('112233:publish-location-selected', {
        detail: { coordinates, zoom, clearDetectedAddress },
      }))
    }

    const geocode = async (query: string) => {
      if (googleMapsTestSdkEnabled) return window.__112233TestAddressGeocode?.(query) ?? []
      await loadGoogleMaps()
      const geocoding = await google.maps.importLibrary('geocoding') as google.maps.GeocodingLibrary
      const response = await new geocoding.Geocoder().geocode({
        address: query,
        bounds: TENERIFE_BOUNDS,
        componentRestrictions: { country: 'ES' },
      })
      return response.results
    }

    const resolveExactAddress = async (version: number, streetOverride = '', showError = false) => {
      const streetInput = document.querySelector<HTMLInputElement>('#publish-street')
      const postcodeInput = document.querySelector<HTMLInputElement>('#publish-postcode')
      const areaInput = document.querySelector<HTMLInputElement>('#publish-area')
      const citySelect = document.querySelector<HTMLSelectElement>('#publish-city')
      const street = (streetOverride || streetInput?.value || '').trim()
      const postcode = (postcodeInput?.value || '').trim()
      const area = (areaInput?.value || '').trim()
      const city = (citySelect?.value || '').trim()
      if (!street || street.length < 3 || !city) return

      const hasBuildingNumber = Boolean(requestedHouseNumber(street))
      const hasFullPostcode = /^\d{5}$/.test(postcode)
      if (!hasBuildingNumber && !hasFullPostcode) return

      const query = [street, postcode, area, city, 'Tenerife', 'Spain'].filter(Boolean).join(', ')
      try {
        const results = await geocode(query)
        if (cancelled || !gate.isCurrent(version)) return
        const result = results.find((candidate) => resultMatchesQuery(candidate, street, postcode, city))
        const coordinates = result ? resultCoordinates(result) : null
        if (!result || !coordinates) {
          if (showError || (hasBuildingNumber && hasFullPostcode)) {
            window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: notFoundMessage } }))
          }
          return
        }
        window.dispatchEvent(new CustomEvent('112233:map-address-resolved', { detail: {
          formattedAddress: result.formatted_address,
          addressComponents: result.address_components,
          coordinates,
        } }))
        dispatchAddressPoint(coordinates, hasBuildingNumber ? EXACT_ADDRESS_ZOOM : STREET_ADDRESS_ZOOM)
      } catch {
        if (!cancelled && gate.isCurrent(version) && showError) {
          window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: notFoundMessage } }))
        }
      }
    }

    const schedule = (streetOverride = '', showError = false) => {
      cancelPending()
      const version = gate.next()
      timer = window.setTimeout(() => {
        timer = undefined
        void resolveExactAddress(version, streetOverride, showError)
      }, ADDRESS_DEBOUNCE_MS)
    }

    const setupInput = (element: HTMLInputElement, kind: 'street' | 'postcode' | 'area') => {
      if (cleanups.has(element)) return
      if (kind === 'area') {
        const onAreaInput = (event: Event) => { if (event.isTrusted) cancelPending() }
        element.addEventListener('input', onAreaInput)
        cleanups.set(element, () => element.removeEventListener('input', onAreaInput))
        return
      }
      const onInput = (event: Event) => {
        if (!event.isTrusted) return
        rawAutocompleteStreet = ''
        schedule('', false)
      }
      const onBlur = (event: Event) => {
        if (!event.isTrusted) return
        schedule('', true)
      }
      element.addEventListener('input', onInput)
      element.addEventListener('blur', onBlur)
      cleanups.set(element, () => {
        element.removeEventListener('input', onInput)
        element.removeEventListener('blur', onBlur)
      })
    }

    const setupMunicipality = (element: HTMLSelectElement) => {
      if (cleanups.has(element)) return
      const onChange = (event: Event) => { if (event.isTrusted) cancelPending() }
      element.addEventListener('change', onChange)
      cleanups.set(element, () => element.removeEventListener('change', onChange))
    }

    const setupAutocomplete = (element: PlaceAutocompleteWithValue) => {
      if (cleanups.has(element)) return
      const onInput = (event: Event) => {
        if (!event.isTrusted) return
        rawAutocompleteStreet = (element.value ?? '').trim()
        if (rawAutocompleteStreet) schedule(rawAutocompleteStreet, false)
      }
      const onBlur = (event: Event) => {
        if (!event.isTrusted) return
        rawAutocompleteStreet = (element.value ?? rawAutocompleteStreet).trim()
        if (rawAutocompleteStreet) schedule(rawAutocompleteStreet, true)
      }
      element.addEventListener('input', onInput)
      element.addEventListener('blur', onBlur)
      cleanups.set(element, () => {
        element.removeEventListener('input', onInput)
        element.removeEventListener('blur', onBlur)
      })
    }

    const setup = () => {
      for (const [element, cleanup] of cleanups) {
        if (element.isConnected) continue
        cleanup()
        cleanups.delete(element)
      }
      const street = document.querySelector<HTMLInputElement>('#publish-street')
      const postcode = document.querySelector<HTMLInputElement>('#publish-postcode')
      const area = document.querySelector<HTMLInputElement>('#publish-area')
      const city = document.querySelector<HTMLSelectElement>('#publish-city')
      const autocomplete = document.querySelector<PlaceAutocompleteWithValue>('.publish-place-autocomplete')
      if (street) setupInput(street, 'street')
      if (postcode) setupInput(postcode, 'postcode')
      if (area) setupInput(area, 'area')
      if (city) setupMunicipality(city)
      if (autocomplete) setupAutocomplete(autocomplete)
    }

    const handleLocationSelected = (event: Event) => {
      const detail = (event as CustomEvent<SelectedLocationDetail>).detail ?? {}
      cancelPending()
      if (!detail.coordinates || detail.zoom != null) return
      const street = document.querySelector<HTMLInputElement>('#publish-street')?.value.trim() ?? ''
      const postcode = document.querySelector<HTMLInputElement>('#publish-postcode')?.value.trim() ?? ''
      const hasBuildingNumber = Boolean(requestedHouseNumber(street))
      const hasFullPostcode = /^\d{5}$/.test(postcode)
      if (!hasBuildingNumber && !hasFullPostcode) return
      const coordinates = detail.coordinates
      queueMicrotask(() => {
        if (!cancelled) dispatchAddressPoint(coordinates, hasBuildingNumber ? EXACT_ADDRESS_ZOOM : STREET_ADDRESS_ZOOM, detail.clearDetectedAddress ?? true)
      })
    }
    window.addEventListener('112233:publish-location-selected', handleLocationSelected)

    const isManualLocationControl = (target: EventTarget | null) => target instanceof Element && Boolean(target.closest(
      '.approximate-location-map, .approximate-location-selector > button, .approximate-location-selector__grid button',
    ))
    const handleManualLocationControl = (event: Event) => {
      if (isManualLocationControl(event.target)) cancelPending()
    }
    document.addEventListener('pointerdown', handleManualLocationControl, true)
    document.addEventListener('click', handleManualLocationControl, true)

    const observer = new MutationObserver(setup)
    observer.observe(document.body, { childList: true, subtree: true })
    setup()

    return () => {
      cancelled = true
      cancelPending()
      observer.disconnect()
      window.removeEventListener('112233:publish-location-selected', handleLocationSelected)
      document.removeEventListener('pointerdown', handleManualLocationControl, true)
      document.removeEventListener('click', handleManualLocationControl, true)
      cleanups.forEach((cleanup) => cleanup())
      cleanups.clear()
    }
  }, [notFoundMessage])

  return null
}
