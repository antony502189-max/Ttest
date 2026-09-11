import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

const smartSource = readFileSync('src/components/publish-smart-address-autocomplete.tsx', 'utf8')
const enhancerSource = readFileSync('src/components/publish-location-enhancer.tsx', 'utf8')
const enhancerCss = readFileSync('src/publish-location-enhancer.css', 'utf8')

test('publish address autocomplete keeps Google predictions and adds Tenerife-aware location ranking', () => {
  expect(enhancerSource).toContain("new places.PlaceAutocompleteElement({})")
  expect(enhancerSource).toContain("autocomplete.includedPrimaryTypes = ['street_address', 'route', 'premise', 'subpremise']")
  expect(enhancerSource).toContain("autocomplete.addEventListener('gmp-select'")
  expect(enhancerSource).toContain('autocomplete.locationRestriction = TENERIFE_BOUNDS')

  expect(smartSource).toContain('navigator.geolocation.getCurrentPosition')
  expect(smartSource).toContain("navigator.permissions.query({ name: 'geolocation' })")
  expect(smartSource).toContain('DEVICE_BIAS_RADIUS_METERS = 5_000')
  expect(smartSource).toContain('MAP_BIAS_RADIUS_METERS = 12_000')
  expect(smartSource).toContain('autocomplete.locationBias = { center: coordinates, radius }')
  expect(smartSource).toContain('autocomplete.locationRestriction = TENERIFE_BOUNDS')
  expect(smartSource).toContain("window.addEventListener('112233:publish-location-selected', onLocationSelected)")
})

test('prediction dropdown is not clipped and is styled as a proper address suggestion list', () => {
  expect(enhancerCss).toContain('overflow: visible;')
  expect(enhancerCss).toContain('.publish-place-autocomplete::part(prediction-list)')
  expect(enhancerCss).toContain('.publish-place-autocomplete::part(prediction-item-main-text)')
  expect(enhancerCss).toContain('.publish-place-autocomplete::part(prediction-item-secondary-text)')
  expect(enhancerCss).toContain('.publish-address-assist')
})

test('granted device location biases the live autocomplete near a Tenerife user without persisting coordinates', async ({ page }) => {
  await page.addInitScript(() => {
    const permission = {
      state: 'granted',
      addEventListener() {},
      removeEventListener() {},
    }
    Object.defineProperty(navigator, 'permissions', {
      configurable: true,
      value: { query: async () => permission },
    })
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: {
        getCurrentPosition(success: PositionCallback) {
          success({
            coords: {
              latitude: 28.2916,
              longitude: -16.6291,
              accuracy: 30,
              altitude: null,
              altitudeAccuracy: null,
              heading: null,
              speed: null,
              toJSON: () => ({}),
            },
            timestamp: Date.now(),
            toJSON: () => ({}),
          } as GeolocationPosition)
        },
      },
    })
  })

  await page.goto('/#/')
  const main = page.locator('main')
  await expect(main).toBeVisible()
  await main.evaluate((container) => {
    const mock = document.createElement('div')
    mock.className = 'publish-place-autocomplete'
    container.append(mock)
  })

  const assist = page.locator('.publish-address-assist')
  await expect(assist).toBeVisible()
  await expect(assist).toHaveAttribute('data-location-bias-source', 'device')

  const state = await page.locator('.publish-place-autocomplete').evaluate((element) => {
    const autocomplete = element as HTMLElement & {
      locationBias?: { center?: { lat?: number; lng?: number }; radius?: number } | null
      locationRestriction?: unknown
      origin?: { lat?: number; lng?: number } | null
      includedRegionCodes?: string[]
      dataset: DOMStringMap
    }
    return {
      source: autocomplete.dataset.locationBiasSource,
      radius: autocomplete.locationBias?.radius,
      center: autocomplete.locationBias?.center,
      restriction: autocomplete.locationRestriction ?? null,
      origin: autocomplete.origin,
      regions: autocomplete.includedRegionCodes,
    }
  })

  expect(state).toEqual({
    source: 'device',
    radius: 5000,
    center: { lat: 28.2916, lng: -16.6291 },
    restriction: null,
    origin: { lat: 28.2916, lng: -16.6291 },
    regions: ['es'],
  })
  expect(smartSource).not.toContain('localStorage.setItem')
  expect(smartSource).not.toContain('sessionStorage.setItem')
})
