import { expect, test, type Page } from '@playwright/test'

const ARMEÑIME_REFERENCE = { lat: 28.12976, lng: -16.75563 }
const CUSTOMER_ADDRESS_REFERENCE = { lat: 28.12909, lng: -16.75657 }

async function openPublishLocation(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
  await page.goto('/#/publicar')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.locator('.approximate-location-map')).toBeVisible()
}

async function currentCenter(page: Page) {
  return page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: center.lat(), lng: center.lng() } : null
  })
}

test('Armeñime area focus uses the corrected real-world area center instead of the old east-shifted point', async ({ page }) => {
  await openPublishLocation(page)
  const area = page.getByLabel('Zona o barrio')
  await area.fill('')
  await area.fill('Armeñime')

  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)
  const center = await currentCenter(page)
  expect(center).not.toBeNull()
  expect(Math.abs(center!.lat - ARMEÑIME_REFERENCE.lat)).toBeLessThan(0.005)
  expect(Math.abs(center!.lng - ARMEÑIME_REFERENCE.lng)).toBeLessThan(0.005)
})

test('Calle José Espronceda 20 + 38678 moves from Armeñime area focus to the matched address point at zoom 18', async ({ page }) => {
  await openPublishLocation(page)
  const area = page.getByLabel('Zona o barrio')
  await area.fill('')
  await area.fill('Armeñime')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)

  await page.evaluate((coordinates) => {
    const holder = window as Window & { __customerAddressQuery?: string }
    window.__112233TestAddressGeocode = async (query) => {
      holder.__customerAddressQuery = query
      return [({
        formatted_address: 'Calle José Espronceda 20, 38678 Armeñime, Adeje, Santa Cruz de Tenerife, Spain',
        types: ['street_address'],
        address_components: [
          { long_name: 'Calle José Espronceda', short_name: 'C. José Espronceda', types: ['route'] },
          { long_name: '20', short_name: '20', types: ['street_number'] },
          { long_name: '38678', short_name: '38678', types: ['postal_code'] },
          { long_name: 'Armeñime', short_name: 'Armeñime', types: ['sublocality_level_1'] },
          { long_name: 'Adeje', short_name: 'Adeje', types: ['administrative_area_level_3'] },
        ],
        geometry: {
          location: { lat: () => coordinates.lat, lng: () => coordinates.lng },
          location_type: 'ROOFTOP',
          viewport: {},
        },
      } as unknown as google.maps.GeocoderResult)]
    }
  }, CUSTOMER_ADDRESS_REFERENCE)

  await page.getByLabel('Calle').fill('Calle José Espronceda 20')
  await page.getByLabel('Código postal').fill('38678')

  await expect.poll(() => page.evaluate(() => (window as Window & { __customerAddressQuery?: string }).__customerAddressQuery ?? '')).toBe(
    'Calle José Espronceda 20, 38678, Armeñime, Adeje, Tenerife, Spain',
  )
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(18)
  await expect.poll(() => currentCenter(page)).toEqual(CUSTOMER_ADDRESS_REFERENCE)
  await expect(page.getByLabel('Municipio')).toHaveValue('Adeje')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Armeñime')
  await expect(page.getByLabel('Calle')).toHaveValue('Calle José Espronceda 20')
  await expect(page.getByLabel('Código postal')).toHaveValue('38678')
})

test('C/ street abbreviation still matches the canonical Google Calle route', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Zona o barrio').fill('Armeñime')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)

  await page.evaluate((coordinates) => {
    window.__112233TestAddressGeocode = async () => [({
      formatted_address: 'Calle José Espronceda 20, 38678 Armeñime, Adeje, Santa Cruz de Tenerife, Spain',
      types: ['street_address'],
      address_components: [
        { long_name: 'Calle José Espronceda', short_name: 'C. José Espronceda', types: ['route'] },
        { long_name: '20', short_name: '20', types: ['street_number'] },
        { long_name: '38678', short_name: '38678', types: ['postal_code'] },
        { long_name: 'Armeñime', short_name: 'Armeñime', types: ['sublocality_level_1'] },
        { long_name: 'Adeje', short_name: 'Adeje', types: ['administrative_area_level_3'] },
      ],
      geometry: {
        location: { lat: () => coordinates.lat, lng: () => coordinates.lng },
        location_type: 'ROOFTOP',
        viewport: {},
      },
    } as unknown as google.maps.GeocoderResult)]
  }, CUSTOMER_ADDRESS_REFERENCE)

  await page.getByLabel('Calle').fill('C/ José Espronceda 20')
  await page.getByLabel('Código postal').fill('38678')

  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(18)
  await expect.poll(() => currentCenter(page)).toEqual(CUSTOMER_ADDRESS_REFERENCE)
  await expect(page.locator('.publish-location-error')).toHaveCount(0)
})
