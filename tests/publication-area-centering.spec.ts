import { expect, test, type Page } from '@playwright/test'

async function openPublishLocation(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
  await page.goto('/#/publicar')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.locator('.approximate-location-map')).toBeVisible()
}

async function currentMapCenter(page: Page) {
  return page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: Number(center.lat().toFixed(4)), lng: Number(center.lng().toFixed(4)) } : null
  })
}

test('municipality selection uses the municipality geometry center instead of the legacy town pin', async ({ page }) => {
  await openPublishLocation(page)

  await page.getByLabel('Municipio').selectOption('Arico')

  await expect(page.getByLabel('Municipio')).toHaveValue('Arico')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(11)
  await expect.poll(() => currentMapCenter(page)).not.toEqual({ lat: 28.1773, lng: -16.481 })
  const center = await currentMapCenter(page)
  expect(center).not.toBeNull()
  expect(center!.lat).toBeGreaterThan(27.9)
  expect(center!.lat).toBeLessThan(28.7)
  expect(center!.lng).toBeGreaterThan(-17.1)
  expect(center!.lng).toBeLessThan(-16.0)
  await expect(page.locator('.approximate-location-selector output')).toContainText(`${center!.lat.toFixed(4)}, ${center!.lng.toFixed(4)}`)
})

test('known barrio input recenters the publication map inside the selected municipality', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Municipio').selectOption('Arona')
  await expect(page.getByLabel('Municipio')).toHaveValue('Arona')
  await page.getByLabel('Calle').fill('Calle vieja 9')
  await page.getByLabel('Código postal').fill('38640')

  await page.getByLabel('Zona o barrio').fill('Los Cristianos')

  await expect.poll(() => currentMapCenter(page), { timeout: 5_000 }).toEqual({ lat: 28.0509, lng: -16.7172 })
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)
  await expect(page.locator('.approximate-location-selector output')).toContainText('28.0509, -16.7172')
  await expect(page.getByLabel('Calle')).toHaveValue('')
  await expect(page.getByLabel('Código postal')).toHaveValue('')
})

test('free-form barrio input falls back to Google geocoding and recenters when the point belongs to the municipality', async ({ page }) => {
  await openPublishLocation(page)
  await page.getByLabel('Municipio').selectOption('Arona')
  await expect(page.getByLabel('Municipio')).toHaveValue('Arona')
  await page.evaluate(() => {
    window.__googleMapsTestGeocode = () => Promise.resolve({
      results: [{
        formatted_address: 'Chayofa, Arona, Tenerife, Spain',
        geometry: { location: { lat: () => 28.075, lng: () => -16.695 } },
        address_components: [
          { long_name: 'Chayofa', short_name: 'Chayofa', types: ['locality'] },
          { long_name: 'Arona', short_name: 'Arona', types: ['administrative_area_level_3'] },
        ],
      } as google.maps.GeocoderResult],
    })
  })

  await page.getByLabel('Zona o barrio').fill('Chayofa')

  await expect.poll(() => currentMapCenter(page), { timeout: 5_000 }).toEqual({ lat: 28.075, lng: -16.695 })
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(13)
  await expect(page.locator('.map-inline-error')).toHaveCount(0)
})
