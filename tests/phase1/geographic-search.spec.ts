import { expect, test } from '@playwright/test'
import { card, fixtures, result, type SearchBody } from './fixtures'

type GeographyRequest = SearchBody & {
  autonomousCommunity?: string
  polygon?: Array<{ latitude: number; longitude: number }>
  minLatitude?: number
  maxLatitude?: number
  minLongitude?: number
  maxLongitude?: number
  center?: { latitude: number; longitude: number }
  radiusKm?: number
}

const madridPolygon = '40.35000,-3.80000;40.35000,-3.60000;40.50000,-3.60000;40.50000,-3.80000'

async function watchSearches(page: import('@playwright/test').Page) {
  const requests: GeographyRequest[] = []
  const errors = await fixtures(page, async (body, route) => {
    requests.push(body as GeographyRequest)
    await route.fulfill({ json: result([card(5)]) })
  })
  return { requests, errors }
}

test('mobile polygon overrides a stale island and community in the server search', async ({ page }) => {
  const { requests, errors } = await watchSearches(page)
  await page.goto(`/#/buscar?q=Adeje&comunidad=05&alquiler=holiday&poligono=${encodeURIComponent(madridPolygon)}`)

  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await expect(page.locator('.m2-result-card').first()).toBeVisible()
  await expect.poll(() => requests.some((request) => request.polygon?.length === 4)).toBe(true)

  const selected = requests.find((request) => request.polygon?.length === 4)!
  expect(selected.query).toBe('España')
  expect(selected.autonomousCommunity).toBeUndefined()
  expect(selected.polygon).toEqual([
    { latitude: 40.35, longitude: -3.8 },
    { latitude: 40.35, longitude: -3.6 },
    { latitude: 40.5, longitude: -3.6 },
    { latitude: 40.5, longitude: -3.8 },
  ])
  expect(selected.minLatitude).toBeUndefined()
  expect(selected.maxLatitude).toBeUndefined()
  expect(errors).toEqual([])
})

test('mobile selected viewport bounds override a previous named city', async ({ page }) => {
  const { requests, errors } = await watchSearches(page)
  await page.goto('/#/buscar?q=Barcelona&norte=40.5&sur=40.3&este=-3.6&oeste=-3.8')
  await expect.poll(() => requests.some((request) => request.minLatitude === 40.3)).toBe(true)
  const selected = requests.find((request) => request.minLatitude === 40.3)!
  expect(selected.query).toBe('España')
  expect(selected.maxLatitude).toBe(40.5)
  expect(selected.minLongitude).toBe(-3.8)
  expect(selected.maxLongitude).toBe(-3.6)
  expect(selected.polygon).toBeUndefined()
  expect(errors).toEqual([])
})

test('a city or community still scopes results; a blank search has no geography constraint', async ({ page }) => {
  const { requests, errors } = await watchSearches(page)
  await page.goto('/#/buscar?q=Madrid&alquiler=long')
  await expect.poll(() => requests.some((request) => request.query === 'Madrid')).toBe(true)
  let chosen = requests[requests.length - 1]
  expect(chosen.polygon).toBeUndefined()
  expect(chosen.minLatitude).toBeUndefined()

  await page.goto('/#/buscar?q=España&comunidad=13')
  await expect.poll(() => requests.some((request) => request.autonomousCommunity === '13')).toBe(true)
  chosen = requests[requests.length - 1]
  expect(chosen.autonomousCommunity).toBe('13')

  await page.goto('/#/buscar')
  await expect.poll(() => requests.some((request) => request.query === 'España' && !request.autonomousCommunity && !request.polygon)).toBe(true)
  chosen = requests[requests.length - 1]
  expect(chosen.query).toBe('España')
  expect(chosen.autonomousCommunity).toBeUndefined()
  expect(chosen.polygon).toBeUndefined()
  expect(chosen.minLatitude).toBeUndefined()
  expect(errors).toEqual([])
})

test('nearby searches scope results by coordinates and radius, not an old city', async ({ page }) => {
  const { requests, errors } = await watchSearches(page)
  await page.goto('/#/buscar?q=Tenerife&cerca=1&lat=40.4168&lng=-3.7038&radio=12')
  await expect.poll(() => requests.some((request) => request.center?.latitude === 40.4168)).toBe(true)
  const selected = requests.find((request) => request.center?.latitude === 40.4168)!
  expect(selected.query).toBe('España')
  expect(selected.center).toEqual({ latitude: 40.4168, longitude: -3.7038 })
  expect(selected.radiusKm).toBe(12)
  expect(errors).toEqual([])
})

test('desktop list sends the same polygon to PostGIS-backed search', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  const { requests, errors } = await watchSearches(page)
  await page.goto(`/#/buscar?q=Adeje&comunidad=05&poligono=${encodeURIComponent(madridPolygon)}`)
  await expect.poll(() => requests.some((request) => request.polygon?.length === 4)).toBe(true)
  const selected = requests.find((request) => request.polygon?.length === 4)!
  expect(selected.query).toBe('España')
  expect(selected.autonomousCommunity).toBeUndefined()
  expect(errors).toEqual([])
})
