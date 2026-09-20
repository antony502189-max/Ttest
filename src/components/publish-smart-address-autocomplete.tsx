import { useEffect } from 'react'
import { useI18n, type Language } from '@/contexts/i18n-context'
import { googleMapsTestSdkEnabled, loadGoogleMaps } from '@/lib/google-maps/loader'
import { TENERIFE_BOUNDS, isInsideTenerife } from '@/lib/tenerife'
import type { Coordinates } from '@/types'

type AddressComponent = { longText?: string; long_name?: string; types: string[] }
type AddressDetail = { formattedAddress?: string; addressComponents?: AddressComponent[]; coordinates?: Coordinates }
type SelectedLocationDetail = { coordinates?: Coordinates }
type TestPrediction = { label: string; detail: AddressDetail }

type Prediction =
  | { kind: 'new'; key: string; label: string; placePrediction: google.maps.places.PlacePrediction }
  | { kind: 'legacy'; key: string; label: string; placeId: string; detail: AddressDetail }
  | { kind: 'geocode'; key: string; label: string; result: google.maps.GeocoderResult }
  | { kind: 'test'; key: string; label: string; detail: AddressDetail }

declare global {
  interface Window {
    __112233TestAddressPredictions?: (query: string) => Promise<TestPrediction[]>
  }
}

type Copy = {
  idle: string
  nearby: string
  loading: string
  empty: string
  fallback: string
  unavailable: string
  outside: string
  selectedError: string
  button: string
  locating: string
  attribution: string
}

const COPY: Record<Language, Copy> = {
  es: {
    idle: 'Escribe una calle, número o dirección completa. Las sugerencias se limitan a Tenerife.',
    nearby: 'Buscaremos primero cerca de la zona seleccionada y siempre dentro de Tenerife.',
    loading: 'Buscando direcciones en Tenerife…',
    empty: 'No hay sugerencias. Puedes escribir la dirección completa y la comprobaremos igualmente.',
    fallback: 'Usamos el buscador compatible de Google Maps para encontrar esta dirección.',
    unavailable: 'Las sugerencias no están disponibles ahora. Puedes escribir la dirección completa igualmente.',
    outside: 'Tu ubicación está fuera de Tenerife; la búsqueda sigue limitada a la isla.',
    selectedError: 'No pudimos resolver esa sugerencia. Prueba otra o escribe la dirección completa.',
    button: 'Usar mi ubicación',
    locating: 'Buscando tu ubicación…',
    attribution: 'Google Maps',
  },
  en: {
    idle: 'Type a street, number, or full address. Suggestions are limited to Tenerife.',
    nearby: 'We will search near the selected area first and always stay within Tenerife.',
    loading: 'Searching addresses in Tenerife…',
    empty: 'No suggestions found. You can still type the full address and we will verify it.',
    fallback: 'Using the compatible Google Maps address search for this query.',
    unavailable: 'Suggestions are unavailable right now. You can still type the full address.',
    outside: 'Your location is outside Tenerife; search remains limited to the island.',
    selectedError: 'We could not resolve that suggestion. Choose another or type the full address.',
    button: 'Use my location',
    locating: 'Finding your location…',
    attribution: 'Google Maps',
  },
  ru: {
    idle: 'Введите улицу, номер дома или полный адрес. Подсказки ограничены Тенерифе.',
    nearby: 'Сначала ищем рядом с выбранной зоной и в любом случае только на Тенерифе.',
    loading: 'Ищем адреса на Тенерифе…',
    empty: 'Подсказок не найдено. Можно ввести полный адрес — мы всё равно проверим его.',
    fallback: 'Используем совместимый поиск адресов Google Maps для этого запроса.',
    unavailable: 'Подсказки сейчас недоступны. Полный адрес всё равно можно ввести вручную.',
    outside: 'Ваше местоположение вне Тенерифе — поиск по-прежнему ограничен островом.',
    selectedError: 'Не удалось открыть эту подсказку. Выберите другую или введите полный адрес.',
    button: 'Использовать моё местоположение',
    locating: 'Определяем местоположение…',
    attribution: 'Google Maps',
  },
}

const INPUT_DEBOUNCE_MS = 260
const MIN_QUERY_LENGTH = 3
const MAX_PREDICTIONS = 5

function component(components: AddressComponent[] = [], type: string) {
  const item = components.find((entry) => entry.types.includes(type))
  return (item?.longText ?? item?.long_name ?? '').trim()
}

function normalizeHouseNumber(value: string) {
  return value.trim().toLocaleLowerCase().replace(/[\s-]+/g, '')
}

function requestedHouseNumber(value: string) {
  const withoutPostcode = value.replace(/\b\d{5}\b/g, ' ')
  const matches = [...withoutPostcode.matchAll(/\b\d+[A-Za-z]?\b/g)]
  const candidate = matches.at(-1)
  if (!candidate || /^0+[A-Za-z]?$/i.test(candidate[0])) return ''
  const index = candidate.index ?? -1
  const prefix = index >= 0 ? withoutPostcode.slice(0, index).trim().replace(/[.,;:/-]+$/, '').trim() : ''
  // A house number must follow an actual street/name fragment. This prevents
  // pasted list prefixes such as "0 Playa de las Américas..." from being
  // treated as a requested building number.
  return /[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]$/u.test(prefix) ? candidate[0] : ''
}

function coordinatesFromResult(result: google.maps.GeocoderResult): Coordinates | null {
  const location = result.geometry?.location
  if (!location) return null
  const lat = typeof location.lat === 'function' ? location.lat() : Number((location as unknown as { lat?: number }).lat)
  const lng = typeof location.lng === 'function' ? location.lng() : Number((location as unknown as { lng?: number }).lng)
  return Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : null
}

function hasRoute(components: AddressComponent[] = []) {
  return components.some((entry) => entry.types.includes('route'))
}

function matchesRequestedBuilding(detail: AddressDetail, query: string) {
  const wantedNumber = requestedHouseNumber(query)
  if (!wantedNumber) return true
  const resolvedNumber = component(detail.addressComponents, 'street_number')
  return Boolean(resolvedNumber) && normalizeHouseNumber(resolvedNumber) === normalizeHouseNumber(wantedNumber)
}

function dedupePredictions(predictions: Prediction[]) {
  const seen = new Set<string>()
  return predictions.filter((prediction) => {
    const key = prediction.label.trim().toLocaleLowerCase()
    if (!key || seen.has(key)) return false
    seen.add(key)
    return true
  }).slice(0, MAX_PREDICTIONS)
}

function detailFromGeocoderResult(result: google.maps.GeocoderResult): AddressDetail | null {
  const coordinates = coordinatesFromResult(result)
  if (!coordinates || !isInsideTenerife(coordinates)) return null
  return {
    formattedAddress: result.formatted_address,
    addressComponents: (result.address_components ?? []) as AddressComponent[],
    coordinates,
  }
}

function ensureUi(input: HTMLInputElement) {
  let list = input.parentElement?.querySelector<HTMLElement>(':scope > .publish-address-predictions') ?? null
  if (!list) {
    list = document.createElement('div')
    list.className = 'publish-address-predictions'
    list.id = 'publish-address-predictions'
    list.setAttribute('role', 'listbox')
    list.hidden = true
    input.insertAdjacentElement('afterend', list)
  }

  let assist = input.parentElement?.querySelector<HTMLElement>(':scope > .publish-address-assist') ?? null
  if (!assist) {
    assist = document.createElement('div')
    assist.className = 'publish-address-assist'
    assist.innerHTML = '<span class="publish-address-assist__status" aria-live="polite"></span><button type="button" class="publish-address-assist__location"></button>'
    list.insertAdjacentElement('afterend', assist)
  }

  return { list, assist }
}

function browserCoordinates(position: GeolocationPosition): Coordinates {
  return { lat: position.coords.latitude, lng: position.coords.longitude }
}

export function PublishSmartAddressAutocomplete() {
  const { language } = useI18n()
  const copy = COPY[language]

  useEffect(() => {
    let cancelled = false
    let activeInput: HTMLInputElement | null = null
    let inputCleanup: (() => void) | null = null
    let locateCleanup: (() => void) | null = null
    let timer: number | undefined
    let requestId = 0
    let activeIndex = -1
    let predictions: Prediction[] = []
    let sessionToken: google.maps.places.AutocompleteSessionToken | null = null
    let legacyService: google.maps.places.AutocompleteService | null = null
    let placesLibrary: google.maps.PlacesLibrary | null = null
    let newApiUnavailable = false
    let preferredOrigin: Coordinates | null = null
    const cache = new Map<string, Prediction[]>()

    const ui = () => activeInput ? ensureUi(activeInput) : null

    const seedPreferredOriginFromMap = () => {
      if (preferredOrigin) return
      const shell = document.querySelector<HTMLElement>('.approximate-location-map-shell[data-location-lat][data-location-lng]')
      if (!shell) return
      const coordinates = {
        lat: Number(shell.dataset.locationLat),
        lng: Number(shell.dataset.locationLng),
      }
      if (Number.isFinite(coordinates.lat) && Number.isFinite(coordinates.lng) && isInsideTenerife(coordinates)) {
        preferredOrigin = coordinates
      }
    }

    const contextualQuery = (query: string) => {
      const trimmed = query.trim()
      if (!trimmed || trimmed.includes(',') || /\b\d{5}\b/.test(trimmed)) return trimmed
      const area = document.querySelector<HTMLInputElement>('#publish-area')?.value.trim() ?? ''
      const city = document.querySelector<HTMLSelectElement>('#publish-city')?.value.trim() ?? ''
      const normalized = trimmed.toLocaleLowerCase()
      const parts = [trimmed]
      if (area && !normalized.includes(area.toLocaleLowerCase())) parts.push(area)
      if (city && city !== '__112233_auto_municipality__' && !normalized.includes(city.toLocaleLowerCase())) parts.push(city)
      return parts.join(', ')
    }

    const setStatus = (message: string, mode: 'island' | 'nearby' | 'fallback' | 'error' = 'island') => {
      const current = ui()
      if (!current) return
      current.assist.dataset.locationBiasSource = mode
      const status = current.assist.querySelector<HTMLElement>('.publish-address-assist__status')
      if (status && status.textContent !== message) status.textContent = message
    }

    const syncLocationButton = (busy = false) => {
      const current = ui()
      const button = current?.assist.querySelector<HTMLButtonElement>('.publish-address-assist__location')
      if (!button) return
      button.hidden = !navigator.geolocation
      button.disabled = busy
      button.textContent = busy ? copy.locating : copy.button
    }

    const cancelPendingQuery = () => {
      requestId += 1
      if (timer !== undefined) window.clearTimeout(timer)
      timer = undefined
    }

    const closeList = () => {
      const current = ui()
      predictions = []
      activeIndex = -1
      if (!current || !activeInput) return
      current.list.replaceChildren()
      current.list.hidden = true
      activeInput.setAttribute('aria-expanded', 'false')
      activeInput.removeAttribute('aria-activedescendant')
    }

    const updateActiveOption = () => {
      const current = ui()
      if (!current || !activeInput) return
      const options = Array.from(current.list.querySelectorAll<HTMLButtonElement>('.publish-address-prediction'))
      options.forEach((option, index) => {
        const active = index === activeIndex
        option.classList.toggle('is-active', active)
        option.setAttribute('aria-selected', active ? 'true' : 'false')
      })
      const selected = activeIndex >= 0 ? options[activeIndex] : undefined
      if (selected) {
        activeInput.setAttribute('aria-activedescendant', selected.id)
        selected.scrollIntoView({ block: 'nearest' })
      } else {
        activeInput.removeAttribute('aria-activedescendant')
      }
    }

    const dispatchResolved = (detail: AddressDetail, requestedValue: string) => {
      if (!detail.coordinates || !isInsideTenerife(detail.coordinates) || !hasRoute(detail.addressComponents) || !matchesRequestedBuilding(detail, requestedValue)) {
        setStatus(copy.selectedError, 'error')
        return false
      }
      window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: '' } }))
      window.dispatchEvent(new CustomEvent('112233:map-address-resolved', { detail }))
      window.dispatchEvent(new CustomEvent('112233:publish-location-selected', { detail: { coordinates: detail.coordinates } }))
      setStatus(preferredOrigin ? copy.nearby : copy.idle, preferredOrigin ? 'nearby' : 'island')
      closeList()
      return true
    }

    const ensurePlaces = async () => {
      if (placesLibrary) return placesLibrary
      await loadGoogleMaps()
      placesLibrary = await google.maps.importLibrary('places') as google.maps.PlacesLibrary
      return placesLibrary
    }

    const ensureToken = async () => {
      const places = await ensurePlaces()
      if (!sessionToken) sessionToken = new places.AutocompleteSessionToken()
      return sessionToken
    }

    const fetchNewPredictions = async (query: string): Promise<Prediction[]> => {
      if (newApiUnavailable) return []
      try {
        const places = await ensurePlaces()
        const token = await ensureToken()
        const request: google.maps.places.AutocompleteRequest = {
          input: query,
          includedRegionCodes: ['es'],
          locationRestriction: TENERIFE_BOUNDS,
          language,
          region: 'es',
          sessionToken: token,
          ...(preferredOrigin ? { origin: preferredOrigin } : {}),
        }
        const { suggestions } = await places.AutocompleteSuggestion.fetchAutocompleteSuggestions(request)
        return dedupePredictions(suggestions.flatMap((suggestion, index) => {
          const placePrediction = suggestion.placePrediction
          if (!placePrediction) return []
          const label = placePrediction.text.toString().trim()
          return label ? [{ kind: 'new' as const, key: `new-${index}-${label}`, label, placePrediction }] : []
        }))
      } catch {
        newApiUnavailable = true
        return []
      }
    }

    const fetchLegacyPredictions = async (query: string): Promise<Prediction[]> => {
      try {
        const places = await ensurePlaces()
        legacyService ??= new places.AutocompleteService()
        const response = await legacyService.getPlacePredictions({
          input: query,
          bounds: TENERIFE_BOUNDS,
          componentRestrictions: { country: 'es' },
          types: ['geocode'],
        })
        const geocoding = await google.maps.importLibrary('geocoding') as google.maps.GeocodingLibrary
        const geocoder = new geocoding.Geocoder()
        const checked = await Promise.all(response.predictions.slice(0, MAX_PREDICTIONS).map(async (prediction, index): Promise<Prediction | null> => {
          const label = prediction.description?.trim() ?? ''
          if (!prediction.place_id || !label) return null
          try {
            const resolved = await geocoder.geocode({ placeId: prediction.place_id })
            const detail = resolved.results.map(detailFromGeocoderResult).find((candidate): candidate is AddressDetail => Boolean(candidate && hasRoute(candidate.addressComponents)))
            return detail
              ? { kind: 'legacy', key: `legacy-${prediction.place_id}-${index}`, label, placeId: prediction.place_id, detail }
              : null
          } catch {
            return null
          }
        }))
        return dedupePredictions(checked.filter((prediction): prediction is Prediction => Boolean(prediction)))
      } catch {
        return []
      }
    }

    const fetchGeocoderPredictions = async (query: string): Promise<Prediction[]> => {
      try {
        await loadGoogleMaps()
        const geocoding = await google.maps.importLibrary('geocoding') as google.maps.GeocodingLibrary
        const response = await new geocoding.Geocoder().geocode({
          address: `${query}, Tenerife, Spain`,
          bounds: TENERIFE_BOUNDS,
          componentRestrictions: { country: 'ES' },
        })
        return dedupePredictions(response.results.flatMap((result, index) => {
          const detail = detailFromGeocoderResult(result)
          if (!detail || !hasRoute(detail.addressComponents)) return []
          const label = result.formatted_address?.trim() ?? ''
          return label ? [{ kind: 'geocode' as const, key: `geocode-${index}-${label}`, label, result }] : []
        }))
      } catch {
        return []
      }
    }

    const fetchPredictions = async (query: string) => {
      if (googleMapsTestSdkEnabled) {
        const mocked = await window.__112233TestAddressPredictions?.(query) ?? []
        return mocked.map((prediction, index) => ({
          kind: 'test' as const,
          key: `test-${index}-${prediction.label}`,
          label: prediction.label,
          detail: prediction.detail,
        }))
      }
      const modern = await fetchNewPredictions(query)
      if (modern.length) return modern
      const legacy = await fetchLegacyPredictions(query)
      if (legacy.length) {
        setStatus(copy.fallback, 'fallback')
        return legacy
      }
      const geocoded = await fetchGeocoderPredictions(query)
      if (geocoded.length) setStatus(copy.fallback, 'fallback')
      return geocoded
    }

    const resolvePrediction = async (prediction: Prediction): Promise<AddressDetail | null> => {
      if (prediction.kind === 'test') return prediction.detail
      if (prediction.kind === 'geocode') return detailFromGeocoderResult(prediction.result)
      if (prediction.kind === 'legacy') return prediction.detail
      const place = prediction.placePrediction.toPlace()
      await place.fetchFields({ fields: ['formattedAddress', 'location', 'addressComponents'] })
      if (!place.location) return null
      const detail: AddressDetail = {
        formattedAddress: place.formattedAddress ?? '',
        addressComponents: (place.addressComponents ?? []) as AddressComponent[],
        coordinates: { lat: place.location.lat(), lng: place.location.lng() },
      }
      sessionToken = null
      return detail
    }

    const selectPrediction = async (prediction: Prediction) => {
      const input = activeInput
      if (!input) return
      const requestedValue = input.value.trim()
      cancelPendingQuery()
      const selectionId = requestId
      closeList()
      try {
        const detail = await resolvePrediction(prediction)
        if (cancelled || activeInput !== input || selectionId !== requestId) return
        // Do not mutate the visible field until the resolved Google result has
        // passed all address/house-number checks. The map-address-resolved
        // listeners update street, postcode, municipality and area together.
        if (!detail || !dispatchResolved(detail, requestedValue)) setStatus(copy.selectedError, 'error')
      } catch {
        if (!cancelled && activeInput === input && selectionId === requestId) setStatus(copy.selectedError, 'error')
      }
    }

    const renderPredictions = (items: Prediction[]) => {
      const current = ui()
      const input = activeInput
      if (!current || !input) return
      predictions = items
      activeIndex = -1
      current.list.replaceChildren()
      if (!items.length) {
        current.list.hidden = true
        input.setAttribute('aria-expanded', 'false')
        setStatus(copy.empty, 'island')
        return
      }

      items.forEach((prediction, index) => {
        const button = document.createElement('button')
        button.type = 'button'
        button.id = `publish-address-prediction-${index}`
        button.className = 'publish-address-prediction'
        button.setAttribute('role', 'option')
        button.setAttribute('aria-selected', 'false')
        const label = document.createElement('span')
        label.className = 'publish-address-prediction__label'
        label.textContent = prediction.label
        button.append(label)
        button.addEventListener('pointerdown', (event) => event.preventDefault())
        button.addEventListener('click', () => { void selectPrediction(prediction) })
        current.list.append(button)
      })
      const attribution = document.createElement('div')
      attribution.className = 'publish-address-predictions__attribution'
      attribution.textContent = copy.attribution
      current.list.append(attribution)
      current.list.hidden = false
      input.setAttribute('aria-expanded', 'true')
    }

    const runQuery = async (query: string, id: number) => {
      seedPreferredOriginFromMap()
      const contextual = contextualQuery(query)
      const cacheKey = `${language}:${preferredOrigin?.lat ?? ""}:${preferredOrigin?.lng ?? ""}:${contextual.toLocaleLowerCase()}`
      const cached = cache.get(cacheKey)
      if (cached) {
        if (!cancelled && id === requestId) renderPredictions(cached)
        return
      }
      setStatus(copy.loading, preferredOrigin ? 'nearby' : 'island')
      try {
        let result = await fetchPredictions(contextual)
        if (!result.length && contextual !== query) result = await fetchPredictions(query)
        if (cancelled || id !== requestId) return
        cache.set(cacheKey, result)
        renderPredictions(result)
      } catch {
        if (!cancelled && id === requestId) {
          closeList()
          setStatus(copy.unavailable, 'error')
        }
      }
    }

    const scheduleQuery = (value: string) => {
      cancelPendingQuery()
      const id = requestId
      const query = value.trim()
      if (query.length < MIN_QUERY_LENGTH) {
        closeList()
        setStatus(preferredOrigin ? copy.nearby : copy.idle, preferredOrigin ? 'nearby' : 'island')
        return
      }
      timer = window.setTimeout(() => {
        timer = undefined
        void runQuery(query, id)
      }, INPUT_DEBOUNCE_MS)
    }

    const bindInput = (input: HTMLInputElement) => {
      if (activeInput === input) return
      inputCleanup?.()
      inputCleanup = null
      locateCleanup?.()
      locateCleanup = null
      closeList()

      document.querySelectorAll('.publish-place-autocomplete').forEach((element) => element.remove())
      input.classList.remove('publish-street-source-input')
      input.dataset.addressAutocomplete = 'native'
      input.autocomplete = 'street-address'
      input.setAttribute('role', 'combobox')
      input.setAttribute('aria-autocomplete', 'list')
      input.setAttribute('aria-controls', 'publish-address-predictions')
      input.setAttribute('aria-expanded', 'false')
      activeInput = input
      seedPreferredOriginFromMap()

      const current = ensureUi(input)
      const status = current.assist.querySelector<HTMLElement>('.publish-address-assist__status')
      if (status) status.textContent = preferredOrigin ? copy.nearby : copy.idle
      syncLocationButton()

      const onInput = (event: Event) => {
        if (!event.isTrusted) return
        scheduleQuery(input.value)
      }
      const onKeyDown = (event: KeyboardEvent) => {
        if (event.key === 'Escape') {
          closeList()
          return
        }
        if (!predictions.length) return
        if (event.key === 'ArrowDown') {
          event.preventDefault()
          activeIndex = (activeIndex + 1) % predictions.length
          updateActiveOption()
        } else if (event.key === 'ArrowUp') {
          event.preventDefault()
          activeIndex = activeIndex <= 0 ? predictions.length - 1 : activeIndex - 1
          updateActiveOption()
        } else if (event.key === 'Enter' && activeIndex >= 0) {
          event.preventDefault()
          void selectPrediction(predictions[activeIndex])
        }
      }
      const onFocus = () => {
        if (predictions.length) {
          current.list.hidden = false
          input.setAttribute('aria-expanded', 'true')
        }
      }
      const onBlur = () => window.setTimeout(() => {
        if (!current.list.matches(':hover') && document.activeElement?.closest('.publish-address-predictions') !== current.list) closeList()
      }, 120)

      input.addEventListener('input', onInput)
      input.addEventListener('keydown', onKeyDown)
      input.addEventListener('focus', onFocus)
      input.addEventListener('blur', onBlur)
      inputCleanup = () => {
        input.removeEventListener('input', onInput)
        input.removeEventListener('keydown', onKeyDown)
        input.removeEventListener('focus', onFocus)
        input.removeEventListener('blur', onBlur)
      }

      const button = current.assist.querySelector<HTMLButtonElement>('.publish-address-assist__location')
      if (button) {
        const onLocate = () => {
          if (!navigator.geolocation) return
          syncLocationButton(true)
          navigator.geolocation.getCurrentPosition(
            (position) => {
              if (cancelled || activeInput !== input) return
              const coordinates = browserCoordinates(position)
              if (isInsideTenerife(coordinates)) {
                preferredOrigin = coordinates
                setStatus(copy.nearby, 'nearby')
              } else {
                preferredOrigin = null
                setStatus(copy.outside, 'island')
              }
              cache.clear()
              syncLocationButton(false)
              if (input.value.trim().length >= MIN_QUERY_LENGTH) scheduleQuery(input.value)
            },
            () => {
              if (!cancelled && activeInput === input) {
                setStatus(copy.unavailable, 'error')
                syncLocationButton(false)
              }
            },
            { enableHighAccuracy: false, timeout: 6_000, maximumAge: 5 * 60_000 },
          )
        }
        button.addEventListener('click', onLocate)
        locateCleanup = () => button.removeEventListener('click', onLocate)
      }
    }

    const setup = () => {
      const input = document.querySelector<HTMLInputElement>('#publish-street')
      if (!input) return
      bindInput(input)
      document.querySelectorAll('.publish-place-autocomplete').forEach((element) => element.remove())
      input.classList.remove('publish-street-source-input')
      input.dataset.addressAutocomplete = 'native'
    }

    const onLocationSelected = (event: Event) => {
      const coordinates = (event as CustomEvent<SelectedLocationDetail>).detail?.coordinates
      if (!coordinates || !isInsideTenerife(coordinates)) return
      cancelPendingQuery()
      closeList()
      preferredOrigin = coordinates
      cache.clear()
      if (activeInput) setStatus(copy.nearby, 'nearby')
    }

    const onDocumentPointerDown = (event: PointerEvent) => {
      if (!(event.target instanceof Element)) return
      if (event.target.closest('#publish-street, .publish-address-predictions, .publish-address-assist')) return
      closeList()
    }

    const observer = new MutationObserver(setup)
    observer.observe(document.body, { childList: true, subtree: true })
    window.addEventListener('112233:publish-location-selected', onLocationSelected)
    document.addEventListener('pointerdown', onDocumentPointerDown, true)
    setup()

    return () => {
      cancelled = true
      cancelPendingQuery()
      observer.disconnect()
      window.removeEventListener('112233:publish-location-selected', onLocationSelected)
      document.removeEventListener('pointerdown', onDocumentPointerDown, true)
      inputCleanup?.()
      locateCleanup?.()
      document.querySelector('.publish-address-predictions')?.remove()
      document.querySelector('.publish-address-assist')?.remove()
      if (activeInput) {
        activeInput.removeAttribute('role')
        activeInput.removeAttribute('aria-autocomplete')
        activeInput.removeAttribute('aria-controls')
        activeInput.removeAttribute('aria-expanded')
        activeInput.removeAttribute('aria-activedescendant')
        if (activeInput.dataset.addressAutocomplete === 'native') delete activeInput.dataset.addressAutocomplete
      }
    }
  }, [copy, language])

  return null
}
