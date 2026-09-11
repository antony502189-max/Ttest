import { useEffect } from 'react'
import { useI18n, type Language } from '@/contexts/i18n-context'
import { TENERIFE_BOUNDS, isInsideTenerife } from '@/lib/tenerife'
import type { Coordinates } from '@/types'

type BiasSource = 'island' | 'device' | 'map'
type SelectedLocationDetail = { coordinates?: Coordinates }
type SmartAutocomplete = google.maps.places.PlaceAutocompleteElement

type Copy = {
  island: string
  device: string
  map: string
  outside: string
  denied: string
  unavailable: string
  button: string
  locating: string
}

const COPY: Record<Language, Copy> = {
  es: {
    island: 'Las sugerencias se limitan a Tenerife. Escribe una calle, número o dirección completa.',
    device: 'Las sugerencias priorizan direcciones cerca de tu ubicación actual.',
    map: 'Las sugerencias priorizan direcciones cerca de la zona que has elegido.',
    outside: 'Tu ubicación está fuera de Tenerife; seguimos mostrando solo direcciones de la isla.',
    denied: 'Ubicación no disponible. Seguimos mostrando solo direcciones de Tenerife.',
    unavailable: 'No pudimos obtener tu ubicación. Seguimos mostrando solo direcciones de Tenerife.',
    button: 'Usar mi ubicación',
    locating: 'Buscando tu ubicación…',
  },
  en: {
    island: 'Suggestions are limited to Tenerife. Type a street, number, or full address.',
    device: 'Suggestions prioritize addresses near your current location.',
    map: 'Suggestions prioritize addresses near the area you selected.',
    outside: 'Your location is outside Tenerife; suggestions remain limited to the island.',
    denied: 'Location is unavailable. Suggestions remain limited to Tenerife.',
    unavailable: 'We could not get your location. Suggestions remain limited to Tenerife.',
    button: 'Use my location',
    locating: 'Finding your location…',
  },
  ru: {
    island: 'Подсказки ограничены Тенерифе. Введите улицу, номер дома или полный адрес.',
    device: 'Подсказки в первую очередь показывают адреса рядом с вашим текущим местоположением.',
    map: 'Подсказки в первую очередь показывают адреса рядом с выбранной вами зоной.',
    outside: 'Вы находитесь за пределами Тенерифе — подсказки по-прежнему ограничены островом.',
    denied: 'Доступ к местоположению недоступен — подсказки по-прежнему ограничены Тенерифе.',
    unavailable: 'Не удалось получить местоположение — подсказки по-прежнему ограничены Тенерифе.',
    button: 'Использовать моё местоположение',
    locating: 'Определяем местоположение…',
  },
}

const DEVICE_BIAS_RADIUS_METERS = 5_000
const MAP_BIAS_RADIUS_METERS = 12_000

function setAutocompleteLocale(autocomplete: SmartAutocomplete, language: Language) {
  autocomplete.includedRegionCodes = ['es']
  autocomplete.requestedRegion = 'es'
  autocomplete.requestedLanguage = language
}

function restrictToTenerife(autocomplete: SmartAutocomplete) {
  autocomplete.locationBias = null
  autocomplete.locationRestriction = TENERIFE_BOUNDS
  autocomplete.origin = null
  autocomplete.dataset.locationBiasSource = 'island'
}

function biasNear(autocomplete: SmartAutocomplete, coordinates: Coordinates, radius: number, source: Exclude<BiasSource, 'island'>) {
  autocomplete.locationRestriction = null
  autocomplete.locationBias = { center: coordinates, radius }
  autocomplete.origin = coordinates
  autocomplete.dataset.locationBiasSource = source
}

function browserCoordinates(position: GeolocationPosition): Coordinates {
  return { lat: position.coords.latitude, lng: position.coords.longitude }
}

function ensureAssist(anchor: HTMLElement) {
  let assist = anchor.parentElement?.querySelector<HTMLElement>(':scope > .publish-address-assist') ?? null
  if (!assist) {
    assist = document.createElement('div')
    assist.className = 'publish-address-assist'
    assist.innerHTML = '<span class="publish-address-assist__status" aria-live="polite"></span><button type="button" class="publish-address-assist__location"></button>'
    anchor.insertAdjacentElement('afterend', assist)
  }
  return assist
}

export function PublishSmartAddressAutocomplete() {
  const { language } = useI18n()
  const copy = COPY[language]

  useEffect(() => {
    let cancelled = false
    let activeAutocomplete: SmartAutocomplete | null = null
    let permissionStatus: PermissionStatus | null = null
    let permissionListener: (() => void) | null = null
    let locateButtonCleanup: (() => void) | null = null
    let currentBiasSource: BiasSource = 'island'

    const setStatus = (message: string, source: BiasSource = currentBiasSource) => {
      const assist = document.querySelector<HTMLElement>('.publish-address-assist')
      if (!assist) return
      assist.dataset.locationBiasSource = source
      const status = assist.querySelector<HTMLElement>('.publish-address-assist__status')
      if (status && status.textContent !== message) status.textContent = message
    }

    const syncButton = (visible: boolean, busy = false) => {
      const button = document.querySelector<HTMLButtonElement>('.publish-address-assist__location')
      if (!button) return
      button.hidden = !visible
      button.disabled = busy
      button.textContent = busy ? copy.locating : copy.button
    }

    const applyIslandRestriction = (message = copy.island) => {
      if (!activeAutocomplete) return
      currentBiasSource = 'island'
      restrictToTenerife(activeAutocomplete)
      setStatus(message, 'island')
    }

    const applyNearbyBias = (coordinates: Coordinates, source: Exclude<BiasSource, 'island'>) => {
      if (!activeAutocomplete || !isInsideTenerife(coordinates)) return false
      currentBiasSource = source
      biasNear(activeAutocomplete, coordinates, source === 'device' ? DEVICE_BIAS_RADIUS_METERS : MAP_BIAS_RADIUS_METERS, source)
      setStatus(source === 'device' ? copy.device : copy.map, source)
      return true
    }

    const requestDeviceLocation = (fromUserGesture: boolean) => {
      if (!navigator.geolocation || !activeAutocomplete) {
        applyIslandRestriction(copy.unavailable)
        syncButton(false)
        return
      }
      syncButton(true, true)
      navigator.geolocation.getCurrentPosition(
        (position) => {
          if (cancelled) return
          const coordinates = browserCoordinates(position)
          if (!isInsideTenerife(coordinates)) {
            applyIslandRestriction(copy.outside)
            syncButton(true)
            return
          }
          applyNearbyBias(coordinates, 'device')
          syncButton(false)
        },
        (error) => {
          if (cancelled) return
          applyIslandRestriction(error.code === error.PERMISSION_DENIED ? copy.denied : copy.unavailable)
          syncButton(!fromUserGesture || error.code !== error.PERMISSION_DENIED)
        },
        { enableHighAccuracy: false, timeout: 6_000, maximumAge: 5 * 60_000 },
      )
    }

    const bindLocationButton = () => {
      locateButtonCleanup?.()
      const button = document.querySelector<HTMLButtonElement>('.publish-address-assist__location')
      if (!button) return
      const onClick = () => requestDeviceLocation(true)
      button.addEventListener('click', onClick)
      locateButtonCleanup = () => button.removeEventListener('click', onClick)
    }

    const setupAutocomplete = (autocomplete: SmartAutocomplete) => {
      if (activeAutocomplete === autocomplete) return
      activeAutocomplete = autocomplete
      setAutocompleteLocale(autocomplete, language)
      restrictToTenerife(autocomplete)
      const assist = ensureAssist(autocomplete)
      assist.dataset.locationBiasSource = 'island'
      setStatus(copy.island, 'island')
      syncButton(Boolean(navigator.geolocation))
      bindLocationButton()

      const onError = () => {
        if (!cancelled) setStatus(copy.unavailable, currentBiasSource)
      }
      autocomplete.addEventListener('gmp-error', onError)

      void (async () => {
        if (!navigator.geolocation || !navigator.permissions?.query) return
        try {
          permissionStatus = await navigator.permissions.query({ name: 'geolocation' })
          if (cancelled || activeAutocomplete !== autocomplete) return
          if (permissionStatus.state === 'granted') requestDeviceLocation(false)
          const onPermissionChange = () => {
            if (cancelled || activeAutocomplete !== autocomplete) return
            if (permissionStatus?.state === 'granted') requestDeviceLocation(false)
            else if (permissionStatus?.state === 'denied') {
              applyIslandRestriction(copy.denied)
              syncButton(false)
            } else {
              applyIslandRestriction(copy.island)
              syncButton(true)
            }
          }
          permissionStatus.addEventListener('change', onPermissionChange)
          permissionListener = () => permissionStatus?.removeEventListener('change', onPermissionChange)
        } catch {
          syncButton(Boolean(navigator.geolocation))
        }
      })()
    }

    const setup = () => {
      const autocomplete = document.querySelector<SmartAutocomplete>('.publish-place-autocomplete')
      if (autocomplete) setupAutocomplete(autocomplete)
    }

    const onLocationSelected = (event: Event) => {
      const coordinates = (event as CustomEvent<SelectedLocationDetail>).detail?.coordinates
      if (!coordinates || !isInsideTenerife(coordinates)) return
      applyNearbyBias(coordinates, 'map')
      syncButton(true)
    }

    const observer = new MutationObserver(setup)
    observer.observe(document.body, { childList: true, subtree: true })
    window.addEventListener('112233:publish-location-selected', onLocationSelected)
    setup()

    return () => {
      cancelled = true
      observer.disconnect()
      window.removeEventListener('112233:publish-location-selected', onLocationSelected)
      permissionListener?.()
      locateButtonCleanup?.()
      document.querySelector('.publish-address-assist')?.remove()
    }
  }, [copy, language])

  return null
}
