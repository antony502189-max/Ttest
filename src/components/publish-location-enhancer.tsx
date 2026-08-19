import { useEffect } from 'react'
import { googleMapsTestSdkEnabled, loadGoogleMaps } from '@/lib/google-maps/loader'
import { TENERIFE_BOUNDS, isInsideTenerife } from '@/lib/tenerife'
import type { Coordinates } from '@/types'
import '@/publish-location-enhancer.css'

type AddressComponent = { longText?: string; long_name?: string; types: string[] }
type AddressDetail = { formattedAddress?: string; addressComponents?: AddressComponent[]; coordinates?: Coordinates }

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
  const street = [route, number].filter(Boolean).join(' ').trim() || detail.formattedAddress?.split(',')[0]?.trim() || ''
  setNativeValue(document.querySelector<HTMLInputElement>('#publish-street'), street)
  setNativeValue(document.querySelector<HTMLInputElement>('#publish-postcode'), postcode)
  setNativeValue(citySelect, city)
  setNativeValue(document.querySelector<HTMLInputElement>('#publish-area'), area)
}

export function PublishLocationEnhancer() {
  useEffect(() => {
    let cancelled = false
    const widgets = new Set<HTMLElement>()

    const handleResolved = (event: Event) => applyAddress((event as CustomEvent<AddressDetail>).detail ?? {})
    window.addEventListener('112233:map-address-resolved', handleResolved)

    const setup = async () => {
      const input = document.querySelector<HTMLInputElement>('#publish-street')
      if (!input || input.dataset.addressAutocomplete) return
      input.dataset.addressAutocomplete = 'pending'
      input.placeholder = 'Empieza a escribir Calle, número…'
      input.autocomplete = 'street-address'
      if (googleMapsTestSdkEnabled) { input.dataset.addressAutocomplete = 'test'; return }
      try {
        await loadGoogleMaps()
        const places = await google.maps.importLibrary('places') as google.maps.PlacesLibrary
        if (cancelled || !input.isConnected) return
        const autocomplete = new places.PlaceAutocompleteElement({})
        autocomplete.classList.add('publish-place-autocomplete')
        autocomplete.placeholder = 'Empieza a escribir Calle, número…'
        autocomplete.includedRegionCodes = ['es']
        autocomplete.locationRestriction = TENERIFE_BOUNDS
        autocomplete.setAttribute('aria-label', 'Calle y número')
        autocomplete.addEventListener('gmp-select', async (rawEvent) => {
          const event = rawEvent as google.maps.places.PlacePredictionSelectEvent
          const place = event.placePrediction.toPlace()
          await place.fetchFields({ fields: ['formattedAddress', 'location', 'addressComponents'] })
          if (!place.location) return
          const coordinates = { lat: place.location.lat(), lng: place.location.lng() }
          if (!isInsideTenerife(coordinates)) return
          const detail: AddressDetail = { formattedAddress: place.formattedAddress ?? '', addressComponents: (place.addressComponents ?? []) as AddressComponent[], coordinates }
          applyAddress(detail)
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
    }
  }, [])
  return null
}
