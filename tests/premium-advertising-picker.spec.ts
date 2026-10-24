import { expect, test } from '@playwright/test'

const availability = (premiumAvailable = 1, regularAvailable = 7) => ({
  total: 7, available: regularAvailable, monthlyPriceCents: 3000,
  premiumAvailable, premiumMonthlyPriceCents: 6000, months: 1, currency: 'EUR',
  pushEnabled: false, pushPublicKey: null,
})

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
  })
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/v1/advertisements/premium', (route) => route.fulfill({ json: [] }))
  await page.route('**/api/v1/advertisements/availability', (route) => route.fulfill({ json: availability() }))
})

test('premium and each regular empty slot show exactly one verified monthly price', async ({ page }) => {
  await page.goto('/#/')
  const ads = page.locator('.commercial-ad--mobile')
  await expect(ads.getByTestId('premium-advertising-banner')).toBeVisible()
  await expect(ads.getByTestId('premium-advertising-price')).toContainText('60')
  await expect(ads.getByTestId('premium-advertising-price')).toContainText('30 días')
  const slots = ads.getByTestId('advertising-slot')
  await expect(slots).toHaveCount(7)
  await expect(ads.getByTestId('advertising-slot-price')).toHaveCount(7)
  for (const item of await ads.getByTestId('advertising-slot-price').all()) {
    await expect(item).toContainText('30')
    await expect(item).toContainText('30 días')
  }
  expect(await ads.evaluate(node => node.scrollWidth <= node.clientWidth)).toBe(true)
})

test('click premium opens two server-priced choices, then forwards chosen plan before creating a charge', async ({ page }) => {
  let checkoutCount = 0
  await page.route('**/api/v1/payments/advertisements/*/checkout', (route) => { checkoutCount++; return route.fulfill({ status: 503, json: {} }) })
  await page.goto('/#/')
  const ads = page.locator('.commercial-ad--mobile')
  await ads.locator('.commercial-ad__premium-action').click()
  const picker = page.getByTestId('advertising-package-picker')
  await expect(picker).toBeVisible()
  await expect(picker.getByRole('button', { name: /60\s*€/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(picker.getByRole('button', { name: /30\s*€/ })).toHaveAttribute('aria-pressed', 'false')

  await picker.getByRole('button', { name: /30\s*€/ }).click()
  await expect(picker.getByRole('button', { name: /30\s*€/ })).toHaveAttribute('aria-pressed', 'true')
  await picker.getByRole('button', { name: 'Continuar' }).click()
  await expect(page).toHaveURL(/#\/publicidad\/nueva\?plan=standard/)
  await expect(page.getByTestId('advertising-editor-package')).toContainText('Espacio publicitario')
  await expect(page.getByTestId('advertising-editor-package')).toContainText('30')
  expect(checkoutCount).toBe(0)

  await page.goto('/#/')
  await ads.locator('.commercial-ad__premium-action').click()
  await picker.getByRole('button', { name: 'Continuar' }).click()
  await expect(page).toHaveURL(/#\/publicidad\/nueva\?plan=premium/)
  await expect(page.getByTestId('advertising-editor-package')).toContainText('Banner Premium Principal')
  await expect(page.getByTestId('advertising-editor-package')).toContainText('60')
  expect(checkoutCount).toBe(0)
})

test('occupied premium slot cannot be purchased while ordinary advertising remains available', async ({ page }) => {
  await page.route('**/api/v1/advertisements/availability', (route) => route.fulfill({ json: availability(0, 7) }))
  await page.goto('/#/')
  const ads = page.locator('.commercial-ad--mobile')
  await expect(ads.locator('.commercial-ad__premium-action')).toBeDisabled()
  await ads.locator('.commercial-ad__slot--empty').first().click()
  const picker = page.getByTestId('advertising-package-picker')
  await expect(picker.getByRole('button', { name: /60\s*€/ })).toBeDisabled()
  await expect(picker.getByRole('button', { name: /30\s*€/ })).toBeEnabled()
  await picker.getByRole('button', { name: 'Continuar' }).click()
  await expect(page).toHaveURL(/#\/publicidad\/nueva\?plan=standard/)
})

test('when the backend tariff is unavailable the app does not invent or offer a charge', async ({ page }) => {
  await page.route('**/api/v1/advertisements/availability', (route) => route.fulfill({ status: 503, json: { detail: 'Unavailable' } }))
  await page.goto('/#/')
  const ads = page.locator('.commercial-ad--mobile')
  await expect(ads.getByTestId('premium-advertising-price')).toHaveCount(0)
  await expect(ads.getByTestId('advertising-slot-price')).toHaveCount(0)
  await expect(ads.locator('.commercial-ad__premium-action')).toBeDisabled()
  await expect(ads.locator('.commercial-ad__slot--empty').first()).toBeDisabled()
})
