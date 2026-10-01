import { expect, request as playwrightRequest, test } from '@playwright/test'
import { listingTestPng } from './media-fixtures'

test('real API persists advertiser upload, checkout and pending review', async ({ page }) => {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const email = `commercial-${id}@example.com`
  const password = 'Correct-Horse-1234'
  const api = await playwrightRequest.newContext({ baseURL: 'http://127.0.0.1:8000', extraHTTPHeaders: { Origin: 'http://127.0.0.1:4174' } })
  const registration = await api.post('/api/v1/auth/register', { data: { name: 'Commercial Advertiser', email, password, role: 'tenant' } })
  expect(registration.status()).toBe(201)
  const account = await registration.json() as { accessToken: string }
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.goto('/#/publicidad/nueva')
  await expect(page).toHaveURL(/#\/acceso$/)
  await page.getByRole('button', { name: 'Iniciar sesión con email' }).click()
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.locator('#login-password').fill(password)
  await page.locator('.m2-auth-form button[type=submit]').click()
  await expect(page).toHaveURL(/#\/publicidad\/nueva$/)
  await page.locator('input[type=file]').setInputFiles({ name: 'banner.png', mimeType: 'image/png', buffer: listingTestPng(id, 0) })
  await page.getByLabel('Título').fill('Commercial moving help')
  await page.getByLabel('Descripción').fill('Safe local moving support throughout Spain.')
  await page.getByLabel('Enlace web').fill('https://example.org/moving')
  await page.getByRole('button', { name: 'Vista previa' }).click()
  await page.getByRole('button', { name: 'Continuar al pago de prueba' }).click()
  await expect(page).toHaveURL(/#\/publicidad\/[0-9a-f-]+\/checkout$/)
  await page.getByRole('button', { name: 'Simular pago' }).click()
  await expect(page).toHaveURL(/#\/mis-campanas$/)
  await expect(page.getByText('Pendiente de revisión')).toBeVisible()
  const ownerImage = page.locator('.ad-flow__row .commercial-ad__visual img')
  await expect(ownerImage).toBeVisible()
  await expect.poll(() => ownerImage.evaluate((node) => {
    const image = node as HTMLImageElement
    return image.complete && image.naturalWidth > 0 && image.naturalHeight > 0
  })).toBe(true)
  await page.reload()
  await expect(page.getByText('Pendiente de revisión')).toBeVisible()
  const reloadedOwnerImage = page.locator('.ad-flow__row .commercial-ad__visual img')
  await expect(reloadedOwnerImage).toBeVisible()
  await expect.poll(() => reloadedOwnerImage.evaluate((node) => {
    const image = node as HTMLImageElement
    return image.complete && image.naturalWidth > 0 && image.naturalHeight > 0
  })).toBe(true)
  const mine = await api.get('/api/v1/advertisements/mine', { headers: { Authorization: `Bearer ${account.accessToken}` } })
  expect(mine.status()).toBe(200)
  const ads = await mine.json() as Array<{ id: string; paymentStatus: string; status: string }>
  expect(ads[0]).toMatchObject({ paymentStatus: 'paid', status: 'pending_review' })
  const publicResponse = await api.get('/api/v1/advertisements/homepage')
  expect((await publicResponse.json() as Array<{ id: string }>).some((item) => item.id === ads[0].id)).toBe(false)
  await api.delete(`/api/v1/advertisements/${ads[0].id}`, { headers: { Authorization: `Bearer ${account.accessToken}` } })
  await api.dispose()
})
