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

const EXACT_ADDRESS_ZOOM = 18
const ADDRESS_DEBOUNCE_MS = 650

function component(result: google.maps.GeocoderResult, type: string) {
  return result.address_components?.find((item) => item.types.includes(type))?.long_name?.trim() ?? ''
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
  const resultTypes = result.types ?? []
  const premiseLike = resultTypes.some((type) => ['street_address', 'premise', 'subpremise'].includes(type))
  if (!route && !premiseLike) return false

  const requestedNumber = street.match(/\b\d+[A-Za-z]?\b/)?.[0] ?? ''
  if (requestedNumber) {
    const resolvedNumber = component(result, 'street_number')
    if (!resolvedNumber && !resultTypes.some((type) => ['premise', 'subpremise'].includes(type))) return false
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

    const dispatchExactPoint = (coordinates: Coordinates, clearDetectedAddress = true) => {
      window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: '' } }))
      window.dispatchEvent(new CustomEvent('112233:publish-location-selected', {
        detail: { coordinates, zoom: EXACT_ADDRESS_ZOOM, clearDetectedAddress },
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

      const hasBuildingNumber = /\b\d+[A-Za-z]?\b/.test(street)
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
        dispatchExactPoint(coordinates)
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
      const onSelect = async (rawEvent: Event) => {
        cancelPending()
        const version = gate.next()
        try {
          const event = rawEvent as google.maps.places.PlacePredictionSelectEvent
          const place = event.placePrediction.toPlace()
          await place.fetchFields({ fields: ['formattedAddress', 'location', 'addressComponents'] })
          if (cancelled || !gate.isCurrent(version) || !place.location) return
          const coordinates = { lat: place.location.lat(), lng: place.location.lng() }
          if (!isInsideTenerife(coordinates)) return
          window.dispatchEvent(new CustomEvent('112233:map-address-resolved', { detail: {
            formattedAddress: place.formattedAddress ?? '',
            addressComponents: place.addressComponents ?? [],
            coordinates,
          } }))
          dispatchExactPoint(coordinates)
        } catch {
          // The original publication autocomplete remains the fallback path.
        }
      }
      element.addEventListener('input', onInput)
      element.addEventListener('blur', onBlur)
      element.addEventListener('gmp-select', onSelect)
      cleanups.set(element, () => {
        element.removeEventListener('input', onInput)
        element.removeEventListener('blur', onBlur)
        element.removeEventListener('gmp-select', onSelect)
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

    const onMapPointerDown = (event: PointerEvent) => {
      if (event.target instanceof Element && event.target.closest('.approximate-location-map')) cancelPending()
    }
    document.addEventListener('pointerdown', onMapPointerDown, true)

    const observer = new MutationObserver(setup)
    observer.observe(document.body, { childList: true, subtree: true })
    setup()

    return () => {
      cancelled = true
      cancelPending()
      observer.disconnect()
      document.removeEventListener('pointerdown', onMapPointerDown, true)
      cleanups.forEach((cleanup) => cleanup())
      cleanups.clear()
    }
  }, [notFoundMessage])

  return null
}
