import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

// Completed user onboarding is refresh-aware; legacy `done` is intentionally only a bypass.
async function finishStartupOnboarding(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
}

test('completed customer onboarding returns after a full browser refresh on mobile shell routes', async ({ page }) => {
  await finishStartupOnboarding(page)
  await expect.poll(() => page.evaluate(() => localStorage.getItem('112233:mobile-onboarding:v1'))).toBe('done:refreshable')

  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await page.reload()

  await expect(page.getByRole('heading', { name: 'Selecciona el idioma de la aplicación' })).toBeVisible()
  const width = await page.evaluate(() => ({ viewport: innerWidth, html: document.documentElement.scrollWidth, body: document.body.scrollWidth }))
  expect(width.html).toBeLessThanOrEqual(width.viewport)
  expect(width.body).toBeLessThanOrEqual(width.viewport)
})

test('legacy done marker remains a deliberate test and migration bypass', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await page.reload()
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Selecciona el idioma de la aplicación' })).toHaveCount(0)
})

test('privacy onboarding step links to the readable Privacy Policy without horizontal overflow', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.getByRole('heading', { name: 'Gracias por instalar nuestra aplicación' })).toBeVisible()

  const policy = page.getByRole('link', { name: 'Política de privacidad' })
  await expect(policy).toBeVisible()
  await expect(policy).toHaveAttribute('href', '#/privacidad')
  await policy.click()

  await expect(page).toHaveURL(/#\/privacidad$/)
  await expect(page.getByRole('heading', { name: 'Política de privacidad' })).toBeVisible()
  await expect(page.getByText(/Datos tratados/)).toBeVisible()
  await expect(page.getByText(/Conservación y derechos/)).toBeVisible()
  const policyWidth = await page.evaluate(() => ({ viewport: innerWidth, html: document.documentElement.scrollWidth, body: document.body.scrollWidth }))
  expect(policyWidth.html).toBeLessThanOrEqual(policyWidth.viewport)
  expect(policyWidth.body).toBeLessThanOrEqual(policyWidth.viewport)
})
