import { useEffect } from 'react'
import { useI18n } from '@/contexts/i18n-context'
import { googleMapsTestSdkEnabled, loadGoogleMaps } from '@/lib/google-maps/loader'
import { loadTenerifeZoneHierarchy, loadTenerifeZones } from '@/lib/map/geojson'
import { getMunicipalityId, getRootMunicipalityId, getZoneFeature, type TenerifeZoneCollection, type TenerifeZoneFeature, type TenerifeZoneGeometry } from '@/lib/map/zones'
import { TENERIFE_BOUNDS, isInsideTenerife, normalizeTenerifeText, resolveTenerifeLocation } from '@/lib/tenerife'
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
const AREA_FOCUS_ZOOM = 13
const AREA_INPUT_DEBOUNCE_MS = 550

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

function pointInRing(point: Coordinates, ring: number[][]) {
  let inside = false
  for (let index = 0, previous = ring.length - 1; index < ring.length; previous = index++) {
    const [x, y] = ring[index]
    const [previousX, previousY] = ring[previous]
    const intersects = (y > point.lat) !== (previousY > point.lat)
      && point.lng < ((previousX - x) * (point.lat - y)) / (previousY - y || Number.EPSILON) + x
    if (intersects) inside = !inside
  }
  return inside
}

function pointInGeometry(point: Coordinates, geometry: TenerifeZoneGeometry) {
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates
  return polygons.some((polygon) => pointInRing(point, polygon[0]) && !polygon.slice(1).some((hole) => pointInRing(point, hole)))
}

function geometryBounds(geometry: TenerifeZoneGeometry) {
  const points = geometry.type === 'Polygon' ? geometry.coordinates.flat() : geometry.coordinates.flat(2)
  let minLat = Number.POSITIVE_INFINITY
  let maxLat = Number.NEGATIVE_INFINITY
  let minLng = Number.POSITIVE_INFINITY
  let maxLng = Number.NEGATIVE_INFINITY
  for (const [lng, lat] of points) {
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue
    minLat = Math.min(minLat, lat)
    maxLat = Math.max(maxLat, lat)
    minLng = Math.min(minLng, lng)
    maxLng = Math.max(maxLng, lng)
  }
  if (![minLat, maxLat, minLng, maxLng].every(Number.isFinite)) return null
  return { minLat, maxLat, minLng, maxLng }
}

function ringCentroid(ring: number[][]): { coordinates: Coordinates; weight: number } | null {
  if (ring.length < 3) return null
  let twiceArea = 0
  let centroidXTimesSixArea = 0
  let centroidYTimesSixArea = 0
  for (let index = 0; index < ring.length; index += 1) {
    const [x1, y1] = ring[index]
    const [x2, y2] = ring[(index + 1) % ring.length]
    const cross = x1 * y2 - x2 * y1
    twiceArea += cross
    centroidXTimesSixArea += (x1 + x2) * cross
    centroidYTimesSixArea += (y1 + y2) * cross
  }
  if (Math.abs(twiceArea) < Number.EPSILON) return null
  return {
    coordinates: {
      lng: centroidXTimesSixArea / (3 * twiceArea),
      lat: centroidYTimesSixArea / (3 * twiceArea),
    },
    weight: Math.abs(twiceArea),
  }
}

function geometryRepresentativeCenter(geometry: TenerifeZoneGeometry): Coordinates | null {
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates
  const weighted = polygons
    .map((polygon) => ringCentroid(polygon[0]))
    .filter((value): value is { coordinates: Coordinates; weight: number } => Boolean(value))
  if (!weighted.length) return null
  const weight = weighted.reduce((sum, value) => sum + value.weight, 0)
  const centroid = {
    lat: weighted.reduce((sum, value) => sum + value.coordinates.lat * value.weight, 0) / weight,
    lng: weighted.reduce((sum, value) => sum + value.coordinates.lng * value.weight, 0) / weight,
  }
  if (pointInGeometry(centroid, geometry)) return centroid

  const bounds = geometryBounds(geometry)
  if (!bounds) return null
  let best: Coordinates | null = null
  let bestDistance = Number.POSITIVE_INFINITY
  const steps = 24
  for (let row = 0; row <= steps; row += 1) {
    const lat = bounds.minLat + ((bounds.maxLat - bounds.minLat) * row) / steps
    for (let column = 0; column <= steps; column += 1) {
      const lng = bounds.minLng + ((bounds.maxLng - bounds.minLng) * column) / steps
      const candidate = { lat, lng }
      if (!pointInGeometry(candidate, geometry)) continue
      const distance = (lat - centroid.lat) ** 2 + (lng - centroid.lng) ** 2
      if (distance < bestDistance) {
        best = candidate
        bestDistance = distance
      }
    }
  }
  return best ?? centroid
}

function municipalityFeature(city: string, collection: TenerifeZoneCollection) {
  const municipalityId = getMunicipalityId(city)
  const sourceMunicipalityId = municipalityId?.replace(/^municipality:/, '')
  return municipalityId
    ? getZoneFeature(municipalityId, collection)
      ?? collection.features.find((candidate) => candidate.properties.kind === 'municipality' && candidate.properties.id === sourceMunicipalityId)
    : undefined
}

function featureMatchesArea(feature: TenerifeZoneFeature, area: string, city: string, collection: TenerifeZoneCollection) {
  if (feature.properties.kind === 'municipality') return false
  const wanted = normalizeTenerifeText(area)
  const labels = [feature.properties.label, ...(feature.properties.aliases ?? [])].map(normalizeTenerifeText)
  if (!labels.includes(wanted)) return false
  return getRootMunicipalityId(feature.properties.id, collection) === getMunicipalityId(city)
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
  setNativeValue(document.querySelector<HTMLInputElement>('#publish-area'), area, { addressSync: true })
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
  const areaNotFoundMessage = language === 'ru' ? 'Не удалось определить этот район внутри выбранного муниципалитета.' : language === 'en' ? 'This area could not be located inside the selected municipality.' : 'No se pudo localizar esta zona dentro del municipio seleccionado.'
  const selectorTitle = language === 'ru' ? 'Выберите примерную точку' : language === 'en' ? 'Select an approximate point' : 'Selecciona un punto aproximado'
  const selectorHelp = language === 'ru' ? 'Маркер расположен в выбранном районе. Его можно немного сдвинуть, не раскрывая точную улицу.' : language === 'en' ? 'The marker is centred in the area. Move it slightly without publishing the exact street.' : 'El marcador se centra en la zona. Muévelo ligeramente sin publicar la calle exacta.'

  useEffect(() => {
    let cancelled = false
    const locationGate = createRequestVersionGate()
    const widgets = new Set<HTMLElement>()
    const municipalityListeners = new Map<HTMLSelectElement, EventListener>()
    const areaListeners = new Map<HTMLInputElement, EventListener>()
    const municipalityTimers = new Set<number>()
    const areaTimers = new Map<HTMLInputElement, number>()

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
      setNativeValue(document.querySelector<HTMLInputElement>('#publish-area'), '', { allowEmpty: true, addressSync: true })
      setNativeValue(document.querySelector<HTMLInputElement>('#publish-street'), '', { allowEmpty: true })
      setNativeValue(document.querySelector<HTMLInputElement>('#publish-postcode'), '', { allowEmpty: true })
      const autocomplete = document.querySelector<StreetFirstAutocomplete>('.publish-place-autocomplete')
      if (autocomplete && 'value' in autocomplete) autocomplete.value = ''
    }

    const clearStaleAddressForArea = () => {
      setNativeValue(document.querySelector<HTMLInputElement>('#publish-street'), '', { allowEmpty: true })
      setNativeValue(document.querySelector<HTMLInputElement>('#publish-postcode'), '', { allowEmpty: true })
      const autocomplete = document.querySelector<StreetFirstAutocomplete>('.publish-place-autocomplete')
      if (autocomplete && 'value' in autocomplete) autocomplete.value = ''
    }

    const resolveMunicipalityCoordinates = async (city: string, version: number): Promise<Coordinates | null> => {
      try {
        const collection = await loadTenerifeZones()
        if (cancelled || !locationGate.isCurrent(version)) return null
        const feature = municipalityFeature(city, collection)
        const center = feature ? geometryRepresentativeCenter(feature.geometry) : null
        if (center && isInsideTenerife(center)) return center
      } catch {
        // Fall through to stable known centers and Google geocoding.
      }

      const known = resolveTenerifeLocation(city)?.coordinates
      if (known && isInsideTenerife(known)) return known

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

    const resolveAreaCoordinates = async (area: string, city: string, version: number): Promise<Coordinates | null> => {
      const trimmedArea = area.trim()
      if (trimmedArea.length < 2) return null

      let municipality: TenerifeZoneFeature | undefined
      let municipalityCollection: TenerifeZoneCollection | null = null
      try {
        municipalityCollection = await loadTenerifeZones()
        if (cancelled || !locationGate.isCurrent(version)) return null
        municipality = municipalityFeature(city, municipalityCollection)
      } catch {
        municipalityCollection = null
      }

      try {
        const hierarchy = await loadTenerifeZoneHierarchy()
        if (cancelled || !locationGate.isCurrent(version)) return null
        const feature = hierarchy.features.find((candidate) => featureMatchesArea(candidate, trimmedArea, city, hierarchy))
        const center = feature ? geometryRepresentativeCenter(feature.geometry) : null
        if (center && isInsideTenerife(center) && (!municipality || pointInGeometry(center, municipality.geometry))) return center
      } catch {
        // Not every municipality has a bundled barrio/district layer. Continue.
      }

      const known = resolveTenerifeLocation(trimmedArea)
      if (known?.coordinates && known.type !== 'municipality' && isInsideTenerife(known.coordinates)
        && (!municipality || pointInGeometry(known.coordinates, municipality.geometry))) return known.coordinates

      try {
        await loadGoogleMaps()
        const geocoding = await google.maps.importLibrary('geocoding') as google.maps.GeocodingLibrary
        const response = await new geocoding.Geocoder().geocode({
          address: `${trimmedArea}, ${city}, Tenerife, Spain`,
          bounds: TENERIFE_BOUNDS,
          componentRestrictions: { country: 'ES' },
        })
        if (cancelled || !locationGate.isCurrent(version)) return null
        for (const result of response.results) {
          const location = result.geometry.location
          if (!location) continue
          const coordinates = { lat: location.lat(), lng: location.lng() }
          if (!isInsideTenerife(coordinates)) continue
          if (municipality && !pointInGeometry(coordinates, municipality.geometry)) continue
          return coordinates
        }
        return null
      } catch {
        return null
      }
    }

    const focusArea = async (input: HTMLInputElement) => {
      if (input.dataset.locationAddressSync === 'true') return
      const area = input.value.trim()
      if (area.length < 2) return
      const city = document.querySelector<HTMLSelectElement>('#publish-city')?.value ?? ''
      if (!city) return
      const version = locationGate.next()
      const coordinates = await resolveAreaCoordinates(area, city, version)
      if (cancelled || !locationGate.isCurrent(version) || input.value.trim() !== area) return
      if (!coordinates) {
        window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: areaNotFoundMessage } }))
        return
      }
      clearStaleAddressForArea()
      window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: '' } }))
      window.dispatchEvent(new CustomEvent('112233:publish-location-selected', {
        detail: { coordinates, zoom: AREA_FOCUS_ZOOM, clearDetectedAddress: true },
      }))
    }

    const setupAreaSync = () => {
      for (const [input, listener] of areaListeners) {
        if (input.isConnected) continue
        input.removeEventListener('input', listener)
        areaListeners.delete(input)
        const timer = areaTimers.get(input)
        if (timer !== undefined) window.clearTimeout(timer)
        areaTimers.delete(input)
      }
      const input = document.querySelector<HTMLInputElement>('#publish-area')
      if (!input || areaListeners.has(input)) return
      const listener: EventListener = () => {
        if (input.dataset.locationAddressSync === 'true') return
        const existing = areaTimers.get(input)
        if (existing !== undefined) window.clearTimeout(existing)
        locationGate.next()
        const timer = window.setTimeout(() => {
          areaTimers.delete(input)
          void focusArea(input)
        }, AREA_INPUT_DEBOUNCE_MS)
        areaTimers.set(input, timer)
      }
      input.addEventListener('input', listener)
      areaListeners.set(input, listener)
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
        areaTimers.forEach((timer) => window.clearTimeout(timer))
        areaTimers.clear()
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
      setupAreaSync()
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
          areaTimers.forEach((timer) => window.clearTimeout(timer))
          areaTimers.clear()
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
      areaListeners.forEach((listener, input) => input.removeEventListener('input', listener))
      areaListeners.clear()
      municipalityTimers.forEach((timer) => window.clearTimeout(timer))
      municipalityTimers.clear()
      areaTimers.forEach((timer) => window.clearTimeout(timer))
      areaTimers.clear()
      widgets.forEach((widget) => widget.remove())
      const input = document.querySelector<HTMLInputElement>('#publish-street')
      if (input) {
        delete input.dataset.addressAutocomplete
        input.classList.remove('publish-street-source-input')
      }
    }
  }, [addressNotFoundMessage, areaNotFoundMessage, ariaLabel, municipalityNotFoundMessage, outsideTenerifeMessage, placeholder, selectorHelp, selectorTitle, streetRequiredMessage])
  return null
}
