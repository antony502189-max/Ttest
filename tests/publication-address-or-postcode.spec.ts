import { expect, test, type Page } from '@playwright/test'

async function openPublishLocation(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
  await page.goto('/#/publicar')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.locator('.approximate-location-map')).toBeVisible()
}

test('a 5-digit postcode alone recenters the map and fills the location without requiring a street', async ({ page }) => {
  await openPublishLocation(page)
  const postcodeCenter = { lat: 28.0718, lng: -16.7256 }

  await page.evaluate(({ postcodeCenter }) => {
    const holder = window as Window & { __addressOrPostcodeQueries?: string[] }
    holder.__addressOrPostcodeQueries = []
    window.__112233TestAddressGeocode = async (query) => {
      holder.__addressOrPostcodeQueries?.push(query)
      return [({
        formatted_address: '38670 Costa Adeje, Adeje, Santa Cruz de Tenerife, Spain',
        types: ['postal_code'],
        address_components: [
          { long_name: '38670', short_name: '38670', types: ['postal_code'] },
          { long_name: 'Costa Adeje', short_name: 'Costa Adeje', types: ['locality'] },
          { long_name: 'Adeje', short_name: 'Adeje', types: ['administrative_area_level_3'] },
          { long_name: 'Santa Cruz de Tenerife', short_name: 'TF', types: ['administrative_area_level_2'] },
        ],
        geometry: {
          location: { lat: () => postcodeCenter.lat, lng: () => postcodeCenter.lng },
          location_type: 'GEOMETRIC_CENTER',
          viewport: {},
        },
      } as unknown as google.maps.GeocoderResult)]
    }
  }, { postcodeCenter })

  await page.getByLabel('Código postal').fill('38670')

  await expect(page.getByLabel('Municipio')).toHaveValue('Adeje')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Costa Adeje')
  await expect(page.getByLabel('Código postal')).toHaveValue('38670')
  await expect(page.locator('#publish-street')).toHaveValue('')
  await expect(page.locator('.map-inline-error')).toHaveCount(0)
  await expect(page.locator('.publish-address-example')).toContainText('solo el código postal de 5 dígitos')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)
  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: Number(center.lat().toFixed(4)), lng: Number(center.lng().toFixed(4)) } : null
  })).toEqual({ lat: 28.0718, lng: -16.7256 })
})

test('an exact typed address ignores untouched draft postcode and falls back without stale municipality or area context', async ({ page }) => {
  await openPublishLocation(page)
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Armeñime')
  await expect(page.getByLabel('Código postal')).toHaveValue('38678')
  await page.getByLabel('Municipio').selectOption('Santa Cruz de Tenerife')

  const exact = { lat: 28.0718, lng: -16.7256 }
  await page.evaluate(({ exact }) => {
    const holder = window as Window & { __addressOrPostcodeQueries?: string[] }
    holder.__addressOrPostcodeQueries = []
    window.__112233TestAddressGeocode = async (query) => {
      holder.__addressOrPostcodeQueries?.push(query)
      if (query.includes('Santa Cruz de Tenerife')) {
        return [({
          formatted_address: 'Calle Lisboa 3, 38660 Costa Adeje, Adeje, Santa Cruz de Tenerife, Spain',
          types: ['street_address'],
          address_components: [
            { long_name: 'Calle Lisboa', short_name: 'Calle Lisboa', types: ['route'] },
            { long_name: '3', short_name: '3', types: ['street_number'] },
            { long_name: '38660', short_name: '38660', types: ['postal_code'] },
            { long_name: 'Costa Adeje', short_name: 'Costa Adeje', types: ['locality'] },
            { long_name: 'Adeje', short_name: 'Adeje', types: ['administrative_area_level_3'] },
          ],
          geometry: {
            location: { lat: () => 28.09, lng: () => -16.73 },
            location_type: 'ROOFTOP',
            viewport: {},
          },
        } as unknown as google.maps.GeocoderResult)]
      }
      return [({
        formatted_address: 'Avenida Siam 3, 38670 Costa Adeje, Adeje, Santa Cruz de Tenerife, Spain',
        types: ['street_address'],
        address_components: [
          { long_name: 'Avenida Siam', short_name: 'Av. Siam', types: ['route'] },
          { long_name: '3', short_name: '3', types: ['street_number'] },
          { long_name: '38670', short_name: '38670', types: ['postal_code'] },
          { long_name: 'Costa Adeje', short_name: 'Costa Adeje', types: ['locality'] },
          { long_name: 'Adeje', short_name: 'Adeje', types: ['administrative_area_level_3'] },
        ],
        geometry: {
          location: { lat: () => exact.lat, lng: () => exact.lng },
          location_type: 'ROOFTOP',
          viewport: {},
        },
      } as unknown as google.maps.GeocoderResult)]
    }
  }, { exact })

  await page.locator('#publish-street').fill('Avenida Siam 3')

  await expect.poll(() => page.evaluate(() => (window as Window & { __addressOrPostcodeQueries?: string[] }).__addressOrPostcodeQueries ?? [])).toContain(
    'Avenida Siam 3, Tenerife, Spain',
  )
  await expect(page.getByLabel('Municipio')).toHaveValue('Adeje')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Costa Adeje')
  await expect(page.getByLabel('Código postal')).toHaveValue('38670')
  await expect(page.locator('#publish-street')).toHaveValue('Avenida Siam 3')
  await expect(page.locator('.map-inline-error')).toHaveCount(0)
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(18)
  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: Number(center.lat().toFixed(4)), lng: Number(center.lng().toFixed(4)) } : null
  })).toEqual({ lat: 28.0718, lng: -16.7256 })
})
