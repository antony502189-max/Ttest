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

test('listing map opens a full-screen interactive street map with route and Street View actions', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/#/habitacion/${encodeURIComponent(internalListingId)}`)
  await page.getByRole('button', { name: 'Abrir mapa de ubicación a pantalla completa' }).click()

  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('heading', { name: 'Ubicación' })).toBeVisible()
  await expect(dialog.locator('.listing-location-dialog__map .listing-location-google-map')).toBeVisible()
  await expect(dialog.getByRole('link', { name: 'Calcular ruta' })).toHaveAttribute('target', '_blank')
  await expect(dialog.getByRole('link', { name: 'Street View' })).toHaveAttribute('target', '_blank')

  const box = await dialog.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.x).toBeLessThanOrEqual(1)
  expect(box!.y).toBeLessThanOrEqual(1)
  expect(box!.width).toBeGreaterThanOrEqual(388)
  expect(box!.height).toBeGreaterThanOrEqual(842)
})
