import { useEffect } from 'react'
import { useI18n } from '@/contexts/i18n-context'
import { googleMapsTestSdkEnabled, loadGoogleMaps } from '@/lib/google-maps/loader'
import { TENERIFE_BOUNDS, isInsideTenerife } from '@/lib/tenerife'
import { createRequestVersionGate } from '@/lib/google-maps/address'
import type { Coordinates } from '@/types'
import '@/publish-location-enhancer.css'

type AddressComponent = { longText?: string; long_name?: string; types: string[] }
type AddressDetail = { formattedAddress?: string; addressComponents?: AddressComponent[]; coordinates?: Coordinates }

type StreetFirstAutocomplete = google.maps.places.PlaceAutocompleteElement & {
  includedPrimaryTypes?: string[]
}

function component(components: AddressComponent[], type: string) {
  const item = components.find((entry) => entry.types.includes(type))
  return (item?.longText ?? item?.long_name ?? '').trim()
}

function setNativeValue(element: HTMLInputElement | HTMLSelectElement | null, value: string) {
  if (!element || !value) return
  if (element instanceof HTMLSelectElement && !Array.from(element.options).some((option) => option.value === value)) return
  const prototype = element instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set
  setter?.call(element, value)
  element.dispatchEvent(new Event('input', { bubbles: true }))
  element.dispatchEvent(new Event('change', { bubbles: true }))
}

function matchingSelectValue(element: HTMLSelectElement | null, candidates: string[]) {
  if (!element) return ''
  const available = new Set(Array.from(element.options, (option) => option.value))
  return candidates.find((candidate) => candidate && available.has(candidate)) ?? ''
}

function applyAddress(detail: AddressDetail) {
  const components = detail.addressComponents ?? []
  const route = component(components, 'route')
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
  // Never turn a municipality, POI or arbitrary formatted-address prefix into
  // a street. If Google did not return a route, retain the user's manual value.
  setNativeValue(document.querySelector<HTMLInputElement>('#publish-street'), street)
  setNativeValue(document.querySelector<HTMLInputElement>('#publish-postcode'), postcode)
  setNativeValue(citySelect, city)
  setNativeValue(document.querySelector<HTMLInputElement>('#publish-area'), area)
  return Boolean(route)
}

export function PublishLocationEnhancer() {
  const { language } = useI18n()
  const placeholder = language === 'ru' ? 'Начните вводить улицу и номер…' : language === 'en' ? 'Start typing street and number…' : 'Empieza a escribir Calle, número…'
  const ariaLabel = language === 'ru' ? 'Улица и номер' : language === 'en' ? 'Street and number' : 'Calle y número'
  const streetRequiredMessage = language === 'ru'
    ? 'Выберите улицу или полный адрес на Тенерифе.'
    : language === 'en'
      ? 'Choose a street or complete address in Tenerife.'
      : 'Selecciona una calle o una dirección completa de Tenerife.'
  const selectorTitle = language === 'ru' ? 'Выберите примерную точку' : language === 'en' ? 'Select an approximate point' : 'Selecciona un punto aproximado'
  const selectorHelp = language === 'ru'
    ? 'Маркер расположен в выбранном районе. Его можно немного сдвинуть, не раскрывая точную улицу.'
    : language === 'en'
      ? 'The marker is centred in the area. Move it slightly without publishing the exact street.'
      : 'El marcador se centra en la zona. Muévelo ligeramente sin publicar la calle exacta.'

  useEffect(() => {
    let cancelled = false
    const requestGate = createRequestVersionGate()
    const widgets = new Set<HTMLElement>()

    const restorePreviousLocationCopy = () => {
      const selector = document.querySelector<HTMLElement>('.approximate-location-selector')
      const legend = selector?.querySelector<HTMLElement>(':scope > legend')
      const help = selector?.querySelector<HTMLElement>(':scope > p')
      if (legend && legend.textContent !== selectorTitle) legend.textContent = selectorTitle
      if (help && help.textContent !== selectorHelp) help.textContent = selectorHelp
    }

    const handleResolved = (event: Event) => applyAddress((event as CustomEvent<AddressDetail>).detail ?? {})
    window.addEventListener('112233:map-address-resolved', handleResolved)

    const setup = async () => {
      restorePreviousLocationCopy()
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
        // Customer reference flow is street-first: surface actual routes and
        // postal addresses before municipalities or generic points of interest.
        autocomplete.includedPrimaryTypes = ['street_address', 'route', 'premise', 'subpremise']
        autocomplete.setAttribute('aria-label', ariaLabel)
        autocomplete.addEventListener('gmp-select', async (rawEvent) => {
          const version = requestGate.next()
          const event = rawEvent as google.maps.places.PlacePredictionSelectEvent
          const place = event.placePrediction.toPlace()
          await place.fetchFields({ fields: ['formattedAddress', 'location', 'addressComponents'] })
          if (cancelled || !requestGate.isCurrent(version)) return
          if (!place.location) {
            window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: 'No se pudo encontrar la dirección seleccionada.' } }))
            return
          }
          const coordinates = { lat: place.location.lat(), lng: place.location.lng() }
          if (!isInsideTenerife(coordinates)) {
            window.dispatchEvent(new CustomEvent('112233:publish-location-error', { detail: { message: 'La dirección debe estar en Tenerife.' } }))
            return
          }
          const detail: AddressDetail = { formattedAddress: place.formattedAddress ?? '', addressComponents: (place.addressComponents ?? []) as AddressComponent[], coordinates }
          if (!applyAddress(detail)) {
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
      widgets.forEach((widget) => widget.remove())
      const input = document.querySelector<HTMLInputElement>('#publish-street')
      if (input) {
        delete input.dataset.addressAutocomplete
        input.classList.remove('publish-street-source-input')
      }
    }
  }, [ariaLabel, placeholder, selectorHelp, selectorTitle, streetRequiredMessage])
  return null
}
