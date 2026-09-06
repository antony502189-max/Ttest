import { expect, test, type Page } from '@playwright/test'

async function openPublishLocation(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
  await page.goto('/#/publicar')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.locator('.approximate-location-map')).toBeVisible()
}

const exactAddressResult = (coordinates: { lat: number; lng: number }): google.maps.GeocoderResult => ({
  formatted_address: 'Calle Londres 5, 38660 Costa Adeje, Santa Cruz de Tenerife, Spain',
  types: ['street_address'],
  address_components: [
    { long_name: 'Calle Londres', short_name: 'C. Londres', types: ['route'] },
    { long_name: '5', short_name: '5', types: ['street_number'] },
    { long_name: '38660', short_name: '38660', types: ['postal_code'] },
    { long_name: 'Costa Adeje', short_name: 'Costa Adeje', types: ['sublocality_level_1'] },
    { long_name: 'Adeje', short_name: 'Adeje', types: ['administrative_area_level_3'] },
  ],
  geometry: {
    location: { lat: () => coordinates.lat, lng: () => coordinates.lng },
    location_type: 'ROOFTOP',
    viewport: {} as google.maps.LatLngBounds,
  },
} as google.maps.GeocoderResult)

test('typing street, building number and postcode moves the owner marker to the exact building at street zoom', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Zona o barrio').fill('Costa Adeje')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)

  const exact = { lat: 28.09123, lng: -16.73561 }
  await page.evaluate(({ coordinates }) => {
    window.__112233TestAddressGeocode = async () => [({
      formatted_address: 'Calle Londres 5, 38660 Costa Adeje, Santa Cruz de Tenerife, Spain',
      types: ['street_address'],
      address_components: [
        { long_name: 'Calle Londres', short_name: 'C. Londres', types: ['route'] },
        { long_name: '5', short_name: '5', types: ['street_number'] },
        { long_name: '38660', short_name: '38660', types: ['postal_code'] },
        { long_name: 'Costa Adeje', short_name: 'Costa Adeje', types: ['sublocality_level_1'] },
        { long_name: 'Adeje', short_name: 'Adeje', types: ['administrative_area_level_3'] },
      ],
      geometry: {
        location: { lat: () => coordinates.lat, lng: () => coordinates.lng },
        location_type: 'ROOFTOP',
        viewport: {},
      },
    } as unknown as google.maps.GeocoderResult)]
  }, { coordinates: exact })

  const street = page.getByLabel('Calle')
  await street.click()
  await page.keyboard.type('Calle Londres 5')
  const postcode = page.getByLabel('Código postal')
  await postcode.click()
  await page.keyboard.type('38660')

  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: Number(center.lat().toFixed(5)), lng: Number(center.lng().toFixed(5)) } : null
  })).toEqual(exact)
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(18)
  await expect(page.locator('.approximate-location-selector output')).toContainText('28.0912, -16.7356')
})

test('publication map is substantially larger on a customer-size mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openPublishLocation(page)

  const shell = page.locator('.approximate-location-map-shell')
  const box = await shell.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.height).toBeGreaterThanOrEqual(350)
  expect(box!.width).toBeGreaterThanOrEqual(330)
})
