import { expect, test, type Page } from '@playwright/test'

const listingId = 'armeñime-luminosa-01'

async function openEditAsHost(page: Page) {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.goto(`/#/mis-anuncios/${encodeURIComponent(listingId)}/editar`)
}

test('listing editing is one long scroll form instead of a paged wizard', async ({ page }) => {
  await openEditAsHost(page)

  await expect(page.getByRole('heading', { name: 'Editar habitación' })).toBeVisible()
  await expect(page.locator('.stepper')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Continuar/i })).toHaveCount(0)
  await expect(page.locator('.listing-edit-section')).toHaveCount(9)

  await expect(page.getByRole('heading', { name: 'Tipo de alquiler' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Ubicación' })).toBeAttached()
  await expect(page.getByRole('heading', { name: 'Habitación y vivienda' })).toBeAttached()
  await expect(page.getByRole('heading', { name: 'Precio, gastos y fianza' })).toBeAttached()
  await expect(page.getByRole('heading', { name: 'Disponibilidad' })).toBeAttached()
  await expect(page.getByRole('heading', { name: 'Convivencia y requisitos' })).toBeAttached()
  await expect(page.getByRole('heading', { name: 'Fotografías' })).toBeAttached()
  await expect(page.getByRole('heading', { name: 'Título y descripción' })).toBeAttached()
  await expect(page.getByRole('heading', { name: 'Contacto' })).toBeAttached()
})

test('photo can be replaced in place without deleting the rest', async ({ page }) => {
  await openEditAsHost(page)
  const photos = page.locator('.upload-grid img')
  await expect(photos.first()).toBeAttached()
  const before = await photos.count()
  expect(before).toBeGreaterThan(0)

  const replace = page.getByRole('button', { name: /Sustituir foto 1/ })
  await expect(replace).toBeAttached()
  await replace.click()
  await page.locator('input[aria-label="Sustituir foto del anuncio"]').setInputFiles({
    name: 'replacement.png',
    mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64'),
  })
  await expect(photos).toHaveCount(before)
})

test('normal publication remains the existing step-by-step wizard', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.goto('/#/publicar')

  await expect(page.locator('.stepper')).toBeVisible()
  await expect(page.getByRole('button', { name: /Continuar/i })).toBeVisible()
  await expect(page.locator('.listing-edit-page')).toHaveCount(0)
})
