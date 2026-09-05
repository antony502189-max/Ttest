import { useEffect } from 'react'
import { useI18n } from '@/contexts/i18n-context'
import { googleMapsTestSdkEnabled, loadGoogleMaps } from '@/lib/google-maps/loader'
import { loadTenerifeZones } from '@/lib/map/geojson'
import { getMunicipalityId, getZoneFeature, type TenerifeZoneGeometry } from '@/lib/map/zones'
import { TENERIFE_BOUNDS, isInsideTenerife, resolveTenerifeLocation } from '@/lib/tenerife'
import { createRequestVersionGate } from '@/lib/google-maps/address'
import type { Coordinates } from '@/types'
import '@/publish-location-enhancer.css'

type AddressComponent = { longText?: string; long_name?: string; types: string[] }
type AddressDetail = { formattedAddress?: string; addressComponents?: AddressComponent[]; coordinates?: Coordinates }
type NativeValueOptions = { allowEmpty?: boolean; addressSync?: boolean }

type StreetFirstAutocomplete = google.maps.places.PlaceAutocompleteElement & {
  includedPrimaryTypes?: string[]
  value?: string
}

const MUNICIPALITY_FOCUS_ZOOM = 11

function component(components: AddressComponent[], type: string) {
  const item = components.find((entry) => entry.types.includes(type))
  return (item?.longText ?? item?.long_name ?? '').trim()
}

function setNativeValue(element: HTMLInputElement | HTMLSelectElement | null, value: string, options: NativeValueOptions = {}) {
  if (!element || (!value && !options.allowEmpty)) return
  if (element instanceof HTMLSelectElement && value && !Array.from(element.options).some((option) => option.value === value)) return
  const prototype = element instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set
  if (options.addressSync) element.dataset.locationAddressSync = 'true'
  try {
    setter?.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
    element.dispatchEvent(new Event('change', { bubbles: true }))
  } finally {
    if (options.addressSync) delete element.dataset.locationAddressSync
  }
}

function matchingSelectValue(element: HTMLSelectElement | null, candidates: string[]) {
  if (!element) return ''
  const available = new Set(Array.from(element.options, (option) => option.value))
  return candidates.find((candidate) => candidate && available.has(candidate)) ?? ''
}

function geometryBoundsCenter(geometry: TenerifeZoneGeometry): Coordinates | null {
  const points = geometry.type === 'Polygon' ? geometry.coordinates.flat() : geometry.coordinates.flat(2)
  if (!points.length) return null
  let minLat = Number.POSITIVE_INFINITY
  let maxLat = Number.NEGATIVE_INFINITY
  let minLng = Number.POSITIVE_INFINITY
  let maxLng = Number.NEGATIVE_INFINITY
  for (const point of points) {
    const [lng, lat] = point
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue
    minLat = Math.min(minLat, lat)
    maxLat = Math.max(maxLat, lat)
    minLng = Math.min(minLng, lng)
    maxLng = Math.max(maxLng, lng)
  }
  if (![minLat, maxLat, minLng, maxLng].every(Number.isFinite)) return null
  return { lat: (minLat + maxLat) / 2, lng: (minLng + maxLng) / 2 }
}

function applyAddress(detail: AddressDetail, requireRoute = false) {
  const components = detail.addressComponents ?? []
  const route = component(components, 'route')
  if (requireRoute && !route) return false

  const number = component(components, 'street_number')
  const postcode = component(components, 'postal_code')
  const locality = component(components, 'locality')
  const municipality = component(components, 'administrative_area_level_3')
  const municipalFallback = component(components, 'administrative_area_level_4')
  const citySelect = document.querySelector<HTMLSelectElement>('#publish-city')
  const city = matchingSelectValue(citySelect, [municipality, municipalFallback, locality])
  const area = component(components, 'sublocality_level_1')
    || component(components, 'sublocality')
    || component(components, 'neighborhood')
    || (locality && locality !== city ? locality : '')
  const street = [route, number].filter(Boolean).join(' ').trim()

  setNativeValue(document.querySelector<HTMLInputElement>('#publish-street'), street)
  setNativeValue(document.querySelector<HTMLInputElement>('#publish-postcode'), postcode)
  setNativeValue(citySelect, city, { addressSync: true })
  setNativeValue(document.querySelector<HTMLInputElement>('#publish-area'), area)
  return Boolean(route)
}

export function PublishLocationEnhancer() {
  const { language } = useI18n()
  const placeholder = language === 'ru' ? 'Начните вводить улицу и номер…' : language === 'en' ? 'Start typing street and number…' : 'Empieza a escribir Calle, número…'
  const ariaLabel = language === 'ru' ? 'Улица и номер' : language === 'en' ? 'Street and number' : 'Calle y número'
  const streetRequiredMessage = language === 'ru' ? 'Выберите улицу или полный адрес на Тенерифе.' : language === 'en' ? 'Choose a street or complete address in Tenerife.' : 'Selecciona una calle o una dirección completa de Tenerife.'
  const addressNotFoundMessage = language === 'ru' ? 'Не удалось найти выбранный адрес.' : language === 'en' ? 'The selected address could not be found.' : 'No se pudo encontrar la dirección seleccionada.'
  const outsideTenerifeMessage = language === 'ru' ? 'Адрес должен находиться на Тенерифе.' : language === 'en' ? 'The address must be in Tenerife.' : 'La dirección debe estar en Tenerife.'
  const municipalityNotFoundMessage = language === 'ru' ? 'Не удалось переместить карту в выбранный муниципалитет. Предыдущее местоположение сохранено.' : language === 'en' ? 'The map could not move to the selected municipality. The previous location was kept.' : 'No se pudo mover el mapa al municipio seleccionado. Se ha conservado la ubicación anterior.'
  const selectorTitle = language === 'ru' ? 'Выберите примерную точку' : language === 'en' ? 'Select an approximate point' : 'Selecciona un punto aproximado'
  const selectorHelp = language === 'ru' ? 'Маркер расположен в выбранном районе. Его можно немного сдвинуть, не раскрывая точную улицу.' : language === 'en' ? 'The marker is centred in the area. Move it slightly without publishing the exact street.' : 'El marcador se centra en la zona. Muévelo ligeramente sin publicar la calle exacta.'

  useEffect(() => {
    let cancelled = false
    const locationGate = createRequestVersionGate()
    const widgets = new Set<HTMLElement>()
    const municipalityListeners = new Map<HTMLSelectElement, EventListener>()
    const municipalityTimers = new Set<number>()

    const restorePreviousLocationCopy = () => {
      const selector = document.querySelector<HTMLElement>('.approximate-location-selector')
      const legend = selector?.querySelector<HTMLElement>(':scope > legend')
      const help = selector?.querySelector<HTMLElement>(':scope > p')
      if (legend && legend.textContent !== selectorTitle) legend.textContent = selectorTitle
      if (help && help.textContent !== selectorHelp) help.textContent = selectorHelp
    }

    const handleResolved = (event: Event) => applyAddress((event as CustomEvent<AddressDetail>).detail ?? {})
    window.addEventListener('112233:map-address-resolved', handleResolved)

    const clearStaleAddressForMunicipality = () => {
      setNativeValue(document.querySelector<HTMLInputElement>('#publish-area'), '', { allowEmpty: true })
      setNativeValue(document.querySelector<HTMLInputElement>('#publish-street'), '', { allowEmpty: true })
      setNativeValue(document.querySelector<HTMLInputElement>('#publish-postcode'), '', { allowEmpty: true })
      const autocomplete = document.querySelector<StreetFirstAutocomplete>('.publish-place-autocomplete')
      if (autocomplete && 'value' in autocomplete) autocomplete.value = ''
    }

    const resolveMunicipalityCoordinates = async (city: string, version: number): Promise<Coordinates | null> => {
      const known = resolveTenerifeLocation(city)?.coordinates
      if (known && isInsideTenerife(known)) return known

      try {
        const collection = await loadTenerifeZones()
        if (cancelled || !locationGate.isCurrent(version)) return null
        const municipalityId = getMunicipalityId(city)
        const feature = municipalityId ? getZoneFeature(municipalityId, collection) : undefined
        const center = feature ? geometryBoundsCenter(feature.geometry) : null
        if (center && isInsideTenerife(center)) return center
      } catch {
        // Fall through to Google geocoding. The bundled municipality geometry is
        // preferred because it is deterministic and covers all 31 municipalities.
      }

      try {
        await loadGoogleMaps()
        const geocoding = await google.maps.importLibrary('geocoding') as google.maps.GeocodingLibrary
        const response = await new geocoding.Geocoder().geocode({ address: `${city}, Tenerife, Spain`, bounds: TENERIFE_BOUNDS, componentRestrictions: { country: 'ES' } })
        if (cancelled || !locationGate.isCurrent(version)) return null
        const location = response.results[0]?.geometry.location
        if (!location) return null
        const coordinates = { lat: location.lat(), lng: location.lng() }
        return isInsideTenerife(coordinates) ? coordinates : null
      } catch {
        return null
      }
    }

    const setupMunicipalitySync = () => {
      for (const [select, listener] of municipalityListeners) {
        if (select.isConnected) continue
        select.removeEventListener('change', listener)
        municipalityListeners.delete(select)
      }
      const select = document.querySelector<HTMLSelectElement>('#publish-city')
      if (!select || municipalityListeners.has(select)) return
      let lastMunicipality = select.value
      const listener: EventListener = (event) => {
        const citySelect = event.currentTarget as HTMLSelectElement
        if (citySelect.dataset.locationAddressSync === 'true') {
          lastMunicipality = citySelect.value
          return
        }
        const city = citySelect.value
        const previousCity = lastMunicipality
        const version = locationGate.next()
        const timer = window.setTimeout(() => {
          municipalityTimers.delete(timer)
          if (cancelled || !locationGate.isCurrent(version)) return
          void (async () => {
            const coordinates = await resolveMunicipalityCoordinates(city, version)
            if (cancelled || !locationGate.isCurrent(version)) return
            if (!coordinates) {
              setNativeValue(citySelect, previousCity, { addressSync: true })
              window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: municipalityNotFoundMessage } }))
              return
            }
            clearStaleAddressForMunicipality()
            lastMunicipality = city
            window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: '' } }))
            window.dispatchEvent(new CustomEvent('112233:publish-location-selected', {
              detail: { coordinates, zoom: MUNICIPALITY_FOCUS_ZOOM, clearDetectedAddress: true },
            }))
          })()
        }, 0)
        municipalityTimers.add(timer)
      }
      select.addEventListener('change', listener)
      municipalityListeners.set(select, listener)
    }

    const setup = async () => {
      restorePreviousLocationCopy()
      setupMunicipalitySync()
      const input = document.querySelector<HTMLInputElement>('#publish-street')
      if (!input || input.dataset.addressAutocomplete) return
      input.dataset.addressAutocomplete = 'pending'
      input.placeholder = placeholder
      input.autocomplete = 'street-address'
      if (googleMapsTestSdkEnabled) { input.dataset.addressAutocomplete = 'test'; return }
      try {
        await loadGoogleMaps()
        const places = await google.maps.importLibrary('places') as google.maps.PlacesLibrary
        if (cancelled || !input.isConnected) return
        const autocomplete = new places.PlaceAutocompleteElement({}) as StreetFirstAutocomplete
        autocomplete.classList.add('publish-place-autocomplete')
        autocomplete.placeholder = placeholder
        autocomplete.includedRegionCodes = ['es']
        autocomplete.locationRestriction = TENERIFE_BOUNDS
        autocomplete.includedPrimaryTypes = ['street_address', 'route', 'premise', 'subpremise']
        autocomplete.setAttribute('aria-label', ariaLabel)
        autocomplete.addEventListener('gmp-select', async (rawEvent) => {
          const version = locationGate.next()
          const event = rawEvent as google.maps.places.PlacePredictionSelectEvent
          const place = event.placePrediction.toPlace()
          await place.fetchFields({ fields: ['formattedAddress', 'location', 'addressComponents'] })
          if (cancelled || !locationGate.isCurrent(version)) return
          if (!place.location) {
            window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: addressNotFoundMessage } }))
            return
          }
          const coordinates = { lat: place.location.lat(), lng: place.location.lng() }
          if (!isInsideTenerife(coordinates)) {
            window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: outsideTenerifeMessage } }))
            return
          }
          const detail: AddressDetail = { formattedAddress: place.formattedAddress ?? '', addressComponents: (place.addressComponents ?? []) as AddressComponent[], coordinates }
          if (!applyAddress(detail, true)) {
            window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: streetRequiredMessage } }))
            return
          }
          window.dispatchEvent(new CustomEvent('112233:publish-location-selected', { detail: { coordinates } }))
        })
        input.insertAdjacentElement('beforebegin', autocomplete)
        input.classList.add('publish-street-source-input')
        input.dataset.addressAutocomplete = 'ready'
        widgets.add(autocomplete)
      } catch {
        input.dataset.addressAutocomplete = 'fallback'
        input.classList.remove('publish-street-source-input')
      }
    }

    const observer = new MutationObserver(() => { void setup() })
    observer.observe(document.body, { childList: true, subtree: true })
    void setup()
    return () => {
      cancelled = true
      observer.disconnect()
      window.removeEventListener('112233:map-address-resolved', handleResolved)
      municipalityListeners.forEach((listener, select) => select.removeEventListener('change', listener))
      municipalityListeners.clear()
      municipalityTimers.forEach((timer) => window.clearTimeout(timer))
      municipalityTimers.clear()
      widgets.forEach((widget) => widget.remove())
      const input = document.querySelector<HTMLInputElement>('#publish-street')
      if (input) {
        delete input.dataset.addressAutocomplete
        input.classList.remove('publish-street-source-input')
      }
    }
  }, [addressNotFoundMessage, ariaLabel, municipalityNotFoundMessage, outsideTenerifeMessage, placeholder, selectorHelp, selectorTitle, streetRequiredMessage])
  return null
}
