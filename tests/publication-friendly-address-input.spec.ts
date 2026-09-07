import { expect, test, type Page } from '@playwright/test'

async function openPublishLocation(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
  await page.goto('/#/publicar')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.locator('.approximate-location-map')).toBeVisible()
  await expect(page.locator('label[for="publish-street"]')).toHaveText('Calle o dirección completa')
}

async function installCustomerAddressGeocoder(page: Page) {
  await page.evaluate(() => {
    const holder = window as Window & { __friendlyAddressQueries?: string[] }
    holder.__friendlyAddressQueries = []
    window.__112233TestAddressGeocode = async (query) => {
      holder.__friendlyAddressQueries?.push(query)
      return [({
        formatted_address: 'Calle José Espronceda 20, 38678 Armeñime, Adeje, Santa Cruz de Tenerife, Spain',
        types: ['street_address'],
        address_components: [
          { long_name: 'Calle José Espronceda', short_name: 'C. José Espronceda', types: ['route'] },
          { long_name: '20', short_name: '20', types: ['street_number'] },
          { long_name: '38678', short_name: '38678', types: ['postal_code'] },
          { long_name: 'Armeñime', short_name: 'Armeñime', types: ['sublocality_level_1'] },
          { long_name: 'Adeje', short_name: 'Adeje', types: ['administrative_area_level_3'] },
          { long_name: 'Santa Cruz de Tenerife', short_name: 'TF', types: ['administrative_area_level_2'] },
        ],
        geometry: {
          location: { lat: () => 28.12909, lng: () => -16.75657 },
          location_type: 'ROOFTOP',
          viewport: {},
        },
      } as unknown as google.maps.GeocoderResult)]
    }
  })
}

test('customer postal-style address auto-corrects province-as-municipality and fills the structured address', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Municipio').selectOption('Santa Cruz de Tenerife')
  await installCustomerAddressGeocoder(page)

  await page.locator('#publish-street').fill('Calle José Espronceda 20. Armeñime Santa Cruz de Tenerife.')

  await expect(page.getByLabel('Municipio')).toHaveValue('Adeje')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Armeñime')
  await expect(page.locator('#publish-street')).toHaveValue('Calle José Espronceda 20')
  await expect(page.getByLabel('Código postal')).toHaveValue('38678')
  await expect(page.locator('.map-inline-error')).toHaveCount(0)
  await expect(page.locator('.publish-address-example')).toContainText('Calle José Espronceda 20, 38678 Armeñime, Adeje')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(18)
  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: Number(center.lat().toFixed(5)), lng: Number(center.lng().toFixed(5)) } : null
  })).toEqual({ lat: 28.12909, lng: -16.75657 })
})

test('postcode embedded in a pasted full address is not mistaken for the building number', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Municipio').selectOption('Santa Cruz de Tenerife')
  await installCustomerAddressGeocoder(page)

  await page.locator('#publish-street').fill('Calle José Espronceda 20, 38678 Armeñime, Santa Cruz de Tenerife')

  await expect(page.locator('#publish-street')).toHaveValue('Calle José Espronceda 20')
  await expect(page.getByLabel('Código postal')).toHaveValue('38678')
  await expect(page.getByLabel('Municipio')).toHaveValue('Adeje')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Armeñime')
  await expect.poll(() => page.evaluate(() => (window as Window & { __friendlyAddressQueries?: string[] }).__friendlyAddressQueries ?? [])).toContain(
    'Calle José Espronceda 20, 38678, Armeñime, Santa Cruz de Tenerife, Tenerife, Spain',
  )
})
