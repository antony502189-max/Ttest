import { expect, test, type Page } from '@playwright/test'

async function openPublishLocation(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
  await page.goto('/#/publicar')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.locator('.approximate-location-map')).toBeVisible()
}

const resolvedAddress = (street: string, postcode: string): google.maps.GeocoderResult => ({
  formatted_address: `${street}, ${postcode} Adeje, Spain`,
  address_components: [
    { long_name: street.replace(/ \d+$/, ''), short_name: street.replace(/ \d+$/, ''), types: ['route'] },
    { long_name: street.match(/\d+$/)?.[0] ?? '', short_name: street.match(/\d+$/)?.[0] ?? '', types: ['street_number'] },
    { long_name: postcode, short_name: postcode, types: ['postal_code'] },
    { long_name: 'Costa Adeje', short_name: 'Costa Adeje', types: ['locality'] },
    { long_name: 'Adeje', short_name: 'Adeje', types: ['administrative_area_level_3'] },
  ],
} as google.maps.GeocoderResult)

test('publication map ignores a late reverse-geocode response after a controlled coordinate update', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Calle').fill('Calle vigente 8')
  await page.getByLabel('Código postal').fill('38660')
  await page.evaluate(() => {
    ;(window as Window & { resolveGeocode?: (value: { results: google.maps.GeocoderResult[] }) => void }).__googleMapsTestGeocode = () => new Promise((resolve) => {
      ;(window as Window & { resolveGeocode?: (value: { results: google.maps.GeocoderResult[] }) => void }).resolveGeocode = resolve
    })
  })

  const map = page.locator('.approximate-location-map')
  const box = await map.boundingBox()
  expect(box).not.toBeNull()
  await map.dblclick({ position: { x: Math.round((box?.width ?? 300) * 0.65), y: Math.round((box?.height ?? 220) * 0.45) } })
  await expect.poll(() => page.evaluate(() => Boolean((window as Window & { resolveGeocode?: unknown }).resolveGeocode))).toBe(true)
  const beforeUpdate = await page.locator('.approximate-location-selector output').textContent()
  await page.locator('.approximate-location-selector__grid button').first().dispatchEvent('click')
  await expect.poll(() => page.locator('.approximate-location-selector output').textContent()).not.toBe(beforeUpdate)
  await page.evaluate((result) => (window as Window & { resolveGeocode?: (value: { results: google.maps.GeocoderResult[] }) => void }).resolveGeocode?.({ results: [result] }), resolvedAddress('Calle antigua 1', '99999'))

  await expect(page.getByLabel('Calle')).toHaveValue('Calle vigente 8')
  await expect(page.getByLabel('Código postal')).toHaveValue('38660')
})

test('address selection synchronizes structured fields and the exact publication map point', async ({ page }) => {
  await openPublishLocation(page)
  const selected = { lat: 28.083, lng: -16.73 }
  await page.evaluate((coordinates) => {
    window.dispatchEvent(new CustomEvent('112233:map-address-resolved', { detail: {
      formattedAddress: 'Avenida V Centenario 1, 38660 Costa Adeje, Spain', coordinates,
      addressComponents: [
        { long_name: 'Avenida V Centenario', types: ['route'] }, { long_name: '1', types: ['street_number'] },
        { long_name: '38660', types: ['postal_code'] }, { long_name: 'Costa Adeje', types: ['locality'] },
        { long_name: 'Adeje', types: ['administrative_area_level_3'] }, { long_name: 'Costa Adeje', types: ['sublocality_level_1'] },
      ],
    } }))
    window.dispatchEvent(new CustomEvent('112233:publish-location-selected', { detail: { coordinates } }))
  }, selected)

  await expect(page.getByLabel('Calle')).toHaveValue('Avenida V Centenario 1')
  await expect(page.getByLabel('Código postal')).toHaveValue('38660')
  await expect(page.getByLabel('Municipio')).toHaveValue('Adeje')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Costa Adeje')
  await expect(page.locator('.approximate-location-selector output')).toContainText('28.0830, -16.7300')
  await expect.poll(() => page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: center.lat(), lng: center.lng() } : null
  })).toEqual(selected)
})

test('map pan leaves publication location and address unchanged', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Calle').fill('Calle estable 5')
  await page.getByLabel('Código postal').fill('38670')
  const before = await page.locator('.approximate-location-selector output').textContent()
  await page.evaluate(() => window.__googleMapsTestLastMap?.panTo({ lat: 28.16, lng: -16.70 }))

  await expect(page.locator('.approximate-location-selector output')).toHaveText(before ?? '')
  await expect(page.getByLabel('Calle')).toHaveValue('Calle estable 5')
  await expect(page.getByLabel('Código postal')).toHaveValue('38670')
})

test('resolved map address updates structured fields while retaining fields absent from Google', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Zona o barrio').fill('Barrio manual')
  await page.evaluate((result) => {
    window.__googleMapsTestGeocode = () => Promise.resolve({ results: [result] })
  }, resolvedAddress('Avenida V Centenario 1', '38660'))
  const map = page.locator('.approximate-location-map')
  const box = await map.boundingBox()
  expect(box).not.toBeNull()
  await map.dblclick({ position: { x: Math.round((box?.width ?? 300) * 0.55), y: Math.round((box?.height ?? 220) * 0.5) } })

  await expect(page.getByLabel('Calle')).toHaveValue('Avenida V Centenario 1')
  await expect(page.getByLabel('Código postal')).toHaveValue('38660')
  await expect(page.getByLabel('Municipio')).toHaveValue('Adeje')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Barrio manual')
})
