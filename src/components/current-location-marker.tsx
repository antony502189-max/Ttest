import { useLayoutEffect } from 'react'
import { toast } from 'sonner'
import { loadGoogleMaps } from '@/lib/google-maps/loader'
import '@/current-location-marker.css'

type MapListener = (
  this: google.maps.Map,
  eventName: string,
  handler: (...args: unknown[]) => void,
) => google.maps.MapsEventListener

type LocationSession = {
  root: HTMLElement
  map: google.maps.Map
  button: HTMLButtonElement | null
  marker: google.maps.marker.AdvancedMarkerElement | null
  accuracyCircle: google.maps.Circle | null
  watchId: number | null
  lastPosition: google.maps.LatLngLiteral | null
  centerOnFirstFix: boolean
  originalRestriction: google.maps.MapRestriction | null | undefined
}

const mapByCanvas = new WeakMap<HTMLElement, google.maps.Map>()
const sessions = new Map<google.maps.Map, LocationSession>()
let captureInstallPromise: Promise<void> | null = null

function installMapCapture() {
  if (captureInstallPromise) return captureInstallPromise

  captureInstallPromise = loadGoogleMaps().then(({ maps }) => {
    const prototype = maps.Map.prototype as unknown as {
      addListener: MapListener
      __currentLocationCaptureInstalled?: boolean
    }
    if (prototype.__currentLocationCaptureInstalled) return

    const originalAddListener = prototype.addListener
    prototype.addListener = function addListener(eventName, handler) {
      const container = this.getDiv()
      if (container instanceof HTMLElement && container.classList.contains('results-map__canvas')) {
        mapByCanvas.set(container, this)
      }
      return Reflect.apply(originalAddListener, this, [eventName, handler]) as google.maps.MapsEventListener
    }
    prototype.__currentLocationCaptureInstalled = true
  })

  return captureInstallPromise
}

function createLocationDot() {
  const marker = document.createElement('span')
  marker.className = 'map-current-location-marker'
  marker.setAttribute('aria-label', 'Tu ubicación actual')
  marker.innerHTML = '<span class="map-current-location-marker__pulse"></span><span class="map-current-location-marker__dot"></span>'
  return marker
}

function cleanupSession(session: LocationSession) {
  if (session.watchId !== null) navigator.geolocation.clearWatch(session.watchId)
  session.marker?.remove()
  session.accuracyCircle?.setMap(null)
  session.button?.classList.remove('is-locating', 'is-location-active')
  session.map.setOptions({ restriction: session.originalRestriction ?? undefined })
  sessions.delete(session.map)
}

function showPosition(session: LocationSession, position: GeolocationPosition) {
  const current = {
    lat: position.coords.latitude,
    lng: position.coords.longitude,
  }
  const accuracy = Math.max(position.coords.accuracy || 0, 12)

  session.lastPosition = current
  session.button?.classList.remove('is-locating')
  session.button?.classList.add('is-location-active')
  session.button?.setAttribute('aria-pressed', 'true')

  if (!session.marker) {
    session.marker = new google.maps.marker.AdvancedMarkerElement({
      map: session.map,
      position: current,
      content: createLocationDot(),
      title: 'Tu ubicación actual',
      zIndex: 10000,
    })
  } else {
    session.marker.map = session.map
    session.marker.position = current
  }

  if (!session.accuracyCircle) {
    session.accuracyCircle = new google.maps.Circle({
      map: session.map,
      center: current,
      radius: accuracy,
      clickable: false,
      fillColor: '#4285f4',
      fillOpacity: .13,
      strokeColor: '#4285f4',
      strokeOpacity: .42,
      strokeWeight: 1,
      zIndex: 1,
    })
  } else {
    session.accuracyCircle.setCenter(current)
    session.accuracyCircle.setRadius(accuracy)
    session.accuracyCircle.setMap(session.map)
  }

  if (session.centerOnFirstFix) {
    session.centerOnFirstFix = false
    // The marketplace itself is Tenerife-only, but the location control must
    // still show the user's real position while the feature is being tested.
    session.map.setOptions({ restriction: null })
    session.map.panTo(current)
    if ((session.map.getZoom() ?? 0) < 15) session.map.setZoom(15)
  }
}

function startTracking(root: HTMLElement, map: google.maps.Map, centerOnFirstFix: boolean) {
  if (!navigator.geolocation) {
    toast.error('Tu navegador no ofrece geolocalización.')
    return
  }

  const button = root.querySelector<HTMLButtonElement>('.map-toolbar__locate')
  const existing = sessions.get(map)
  if (existing) {
    existing.centerOnFirstFix ||= centerOnFirstFix
    existing.button = button
    if (existing.lastPosition && centerOnFirstFix) {
      map.setOptions({ restriction: null })
      map.panTo(existing.lastPosition)
      if ((map.getZoom() ?? 0) < 15) map.setZoom(15)
      existing.centerOnFirstFix = false
    }
    return
  }

  const session: LocationSession = {
    root,
    map,
    button,
    marker: null,
    accuracyCircle: null,
    watchId: null,
    lastPosition: null,
    centerOnFirstFix,
    originalRestriction: map.get('restriction') as google.maps.MapRestriction | null | undefined,
  }
  sessions.set(map, session)
  button?.classList.add('is-locating')

  session.watchId = navigator.geolocation.watchPosition(
    (position) => showPosition(session, position),
    (error) => {
      session.button?.classList.remove('is-locating')
      if (error.code === error.PERMISSION_DENIED) toast.error('Разреши доступ к геолокации в настройках браузера.')
      else toast.error('Не удалось определить текущее местоположение.')
      cleanupSession(session)
    },
    {
      enableHighAccuracy: true,
      maximumAge: 3000,
      timeout: 15000,
    },
  )
}

function findResultsMapRoot(target: EventTarget | null) {
  if (!(target instanceof Element)) return null
  return target.closest<HTMLElement>('.results-map')
}

function startForRoot(root: HTMLElement, centerOnFirstFix: boolean, attempts = 0) {
  const canvas = root.querySelector<HTMLElement>('.results-map__canvas')
  const map = canvas ? mapByCanvas.get(canvas) : undefined
  if (map) {
    startTracking(root, map, centerOnFirstFix)
    return
  }
  if (attempts < 40) requestAnimationFrame(() => startForRoot(root, centerOnFirstFix, attempts + 1))
}

export function CurrentLocationMarker() {
  useLayoutEffect(() => {
    let disposed = false
    const nearRequested = window.location.hash.includes('cerca=1')

    void installMapCapture().then(async () => {
      if (disposed) return
      const roots = [...document.querySelectorAll<HTMLElement>('.results-map')]
      if (nearRequested) roots.forEach((root) => startForRoot(root, true))

      try {
        const permission = await navigator.permissions?.query({ name: 'geolocation' })
        if (!disposed && permission?.state === 'granted') {
          roots.forEach((root) => startForRoot(root, false))
        }
      } catch {
        // The Permissions API is optional; the locate button still works.
      }
    }).catch(() => undefined)

    const handleLocateClick = (event: MouseEvent) => {
      if (!(event.target instanceof Element)) return
      const button = event.target.closest<HTMLButtonElement>('.map-toolbar__locate')
      if (!button) return
      const root = findResultsMapRoot(button)
      if (!root) return

      event.preventDefault()
      event.stopImmediatePropagation()
      startForRoot(root, true)
    }

    const observer = new MutationObserver(() => {
      sessions.forEach((session) => {
        if (!session.root.isConnected) cleanupSession(session)
      })
    })

    document.addEventListener('click', handleLocateClick, true)
    observer.observe(document.body, { childList: true, subtree: true })

    return () => {
      disposed = true
      document.removeEventListener('click', handleLocateClick, true)
      observer.disconnect()
      ;[...sessions.values()].forEach(cleanupSession)
    }
  }, [])

  return null
}
