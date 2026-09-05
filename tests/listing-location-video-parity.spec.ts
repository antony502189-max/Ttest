import { expect, test } from '@playwright/test'

const internalListingId = 'armeñime-luminosa-01'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('listing location follows the customer street-map interaction without exposing an exact address', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}`)

  const location = page.locator('.listing-location-section')
  await expect(location).toBeVisible()
  await expect(location.getByRole('heading', { name: 'Ubicación aproximada' })).toBeVisible()
  await expect(location).toContainText('calles y referencias de la zona')
  await expect(location.getByRole('link', { name: 'Calcular ruta' })).toHaveAttribute('href', /google\.com\/maps\/dir\/\?api=1&destination=/)
  await expect(location.getByRole('link', { name: 'Street View' })).toHaveAttribute('href', /map_action=pano&viewpoint=/)
  await expect(location.getByRole('button', { name: 'Abrir mapa de ubicación a pantalla completa' })).toBeVisible()
  await expect(location.locator('.listing-location-google-map')).toHaveAttribute('aria-label', 'Mapa de la ubicación aproximada del anuncio')

  // The public card keeps the privacy contract from the publication sync work:
  // no owner-only street/postcode fields are rendered as the visible location.
  await expect(location).not.toContainText(/386\d{2}/)
  await expect(location).not.toContainText(/Calle\s+\S+\s+\d+/i)
})

test('listing map opens a full-screen zoomable Google roadmap at street level', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}`)
  await page.getByRole('button', { name: 'Abrir mapa de ubicación a pantalla completa' }).click()

  const dialog = page.getByRole('dialog')
  const mapCanvas = dialog.locator('.listing-location-dialog__map .listing-location-google-map')
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('heading', { name: 'Ubicación' })).toBeVisible()
  await expect(mapCanvas).toBeVisible()
  await expect(dialog.getByRole('link', { name: 'Calcular ruta' })).toHaveAttribute('target', '_blank')
  await expect(dialog.getByRole('link', { name: 'Street View' })).toHaveAttribute('target', '_blank')

  const options = await page.evaluate(() => {
    const map = window.__googleMapsTestLastMap
    return map ? {
      zoom: map.get('zoom'),
      minZoom: map.get('minZoom'),
      maxZoom: map.get('maxZoom'),
      mapTypeId: map.get('mapTypeId'),
      zoomControl: map.get('zoomControl'),
      streetViewControl: map.get('streetViewControl'),
      gestureHandling: map.get('gestureHandling'),
    } : null
  })
  expect(options).toEqual({
    zoom: 18,
    minZoom: 11,
    maxZoom: 20,
    mapTypeId: 'roadmap',
    zoomControl: true,
    streetViewControl: true,
    gestureHandling: 'greedy',
  })

  const beforeZoom = await page.evaluate(() => window.__googleMapsTestLastMap?.getZoom() ?? 0)
  await mapCanvas.dispatchEvent('wheel', { deltaY: -100 })
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom() ?? 0)).toBeGreaterThan(beforeZoom)

  const box = await dialog.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.x).toBeLessThanOrEqual(1)
  expect(box!.y).toBeLessThanOrEqual(1)
  expect(box!.width).toBeGreaterThanOrEqual(388)
  expect(box!.height).toBeGreaterThanOrEqual(842)
})

test('customer Android recording viewport keeps the location map edge-to-edge', async ({ page }) => {
  await page.setViewportSize({ width: 588, height: 1280 })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}`)
  await page.getByRole('button', { name: 'Abrir mapa de ubicación a pantalla completa' }).click()

  const dialog = page.getByRole('dialog')
  const mapShell = dialog.locator('.listing-location-dialog__map .listing-location-google-map-shell')
  await expect(dialog).toBeVisible()
  await expect(mapShell).toBeVisible()

  const dialogBox = await dialog.boundingBox()
  const mapBox = await mapShell.boundingBox()
  expect(dialogBox).not.toBeNull()
  expect(mapBox).not.toBeNull()
  expect(dialogBox!.x).toBeLessThanOrEqual(1)
  expect(dialogBox!.y).toBeLessThanOrEqual(1)
  expect(dialogBox!.width).toBeGreaterThanOrEqual(586)
  expect(dialogBox!.height).toBeGreaterThanOrEqual(1278)
  expect(mapBox!.x).toBeLessThanOrEqual(1)
  expect(mapBox!.width).toBeGreaterThanOrEqual(586)

  const layout = await dialog.evaluate((element) => {
    const style = getComputedStyle(element)
    return {
      position: style.position,
      left: style.left,
      right: style.right,
      maxWidth: style.maxWidth,
      transform: style.transform,
    }
  })
  expect(layout.position).toBe('fixed')
  expect(layout.left).toBe('0px')
  expect(layout.right).toBe('0px')
  expect(layout.maxWidth).toBe('588px')
  expect(layout.transform).toBe('none')
})

test('customer location controls are fully localized in English and Russian', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}`)
  const location = page.locator('.listing-location-section')
  const languageSwitcher = page.locator('.language-switcher:visible')

  await languageSwitcher.click()
  await page.getByRole('menuitemradio', { name: /English/ }).click()
  await expect(location.getByRole('heading', { name: 'Approximate location' })).toBeVisible()
  await expect(location).toContainText('nearby streets and landmarks')
  await expect(location.getByRole('link', { name: 'Get directions' })).toBeVisible()
  await expect(location.getByRole('button', { name: 'Open the location map full screen' })).toBeVisible()
  await expect(location.locator('.listing-location-google-map')).toHaveAttribute('aria-label', 'Map of the listing’s approximate location')

  await languageSwitcher.click()
  await page.getByRole('menuitemradio', { name: /Русский/ }).click()
  await expect(location.getByRole('heading', { name: 'Примерное местоположение' })).toBeVisible()
  await expect(location).toContainText('улицы и ориентиры района')
  await expect(location.getByRole('link', { name: 'Построить маршрут' })).toBeVisible()
  await expect(location.getByRole('button', { name: 'Открыть карту местоположения на весь экран' })).toBeVisible()
  await expect(location.locator('.listing-location-google-map')).toHaveAttribute('aria-label', 'Карта примерного местоположения объявления')
})
