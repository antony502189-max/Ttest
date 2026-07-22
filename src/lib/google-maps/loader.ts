import { importLibrary, setOptions } from '@googlemaps/js-api-loader'

const apiKey = (import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? '').trim()
const configuredMapId = (import.meta.env.VITE_GOOGLE_MAPS_MAP_ID ?? '').trim()
export const GOOGLE_MAPS_AUTH_FAILURE_EVENT = '112233:google-maps-auth-failure'

export const googleMapsConfig = {
  hasApiKey: Boolean(apiKey),
  hasProductionMapId: Boolean(configuredMapId),
  mapId: configuredMapId || (import.meta.env.DEV ? 'DEMO_MAP_ID' : ''),
  usesDevelopmentMapId: !configuredMapId && import.meta.env.DEV,
} as const

export class GoogleMapsSetupError extends Error {
  readonly reason: 'missing-key' | 'missing-map-id' | 'load-failed'

  constructor(reason: 'missing-key' | 'missing-map-id' | 'load-failed') {
    super(reason)
    this.name = 'GoogleMapsSetupError'
    this.reason = reason
  }
}

export interface GoogleMapsLibraries {
  maps: google.maps.MapsLibrary
  marker: google.maps.MarkerLibrary
}

let librariesPromise: Promise<GoogleMapsLibraries> | null = null
let optionsSet = false

export function loadGoogleMaps(): Promise<GoogleMapsLibraries> {
  if (!apiKey) return Promise.reject(new GoogleMapsSetupError('missing-key'))
  if (!librariesPromise) {
    if (!optionsSet) {
      const authWindow = window as Window & { gm_authFailure?: () => void }
      authWindow.gm_authFailure = () => window.dispatchEvent(new Event(GOOGLE_MAPS_AUTH_FAILURE_EVENT))
      setOptions({
        key: apiKey,
        v: 'weekly',
        language: 'es',
        region: 'ES',
        authReferrerPolicy: 'origin',
        ...(configuredMapId ? { mapIds: [configuredMapId] } : {}),
      })
      optionsSet = true
    }
    librariesPromise = Promise.all([importLibrary('maps'), importLibrary('marker')])
      .then(([maps, marker]) => ({ maps, marker }))
      .catch(() => {
        librariesPromise = null
        throw new GoogleMapsSetupError('load-failed')
      })
  }
  return librariesPromise
}

export const googleMapsAuthErrorMessage = 'La clave de Google Maps no autoriza este dominio. Revisa las restricciones HTTP referrer en Google Cloud.'

export function googleMapsErrorMessage(error: unknown) {
  if (error instanceof GoogleMapsSetupError && error.reason === 'missing-key') {
    return 'Configura VITE_GOOGLE_MAPS_API_KEY en .env.local para mostrar el mapa.'
  }
  if (error instanceof GoogleMapsSetupError && error.reason === 'missing-map-id') {
    return 'Configura VITE_GOOGLE_MAPS_MAP_ID para usar marcadores avanzados en producci\u00f3n.'
  }
  return 'Google Maps no pudo cargarse. Revisa que Maps JavaScript API est\u00e9 habilitada y que este dominio est\u00e9 permitido.'
}
