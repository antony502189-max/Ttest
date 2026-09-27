import { expect, test } from '@playwright/test'

test('mobile Home and list defer map implementation until map is opened', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const fetched: string[] = []
  page.on('request', (request) => fetched.push(request.url()))
  await page.goto('/')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
  await page.locator('.m2-mode-switch > button').first().click()
  await page.getByTestId('open-location').click()
  await expect(page.getByTestId('mobile-results').locator('.m2-result-card').first()).toBeVisible()
  expect(fetched.some((url) => /mobile-map-listings-layer|google-maps\/loader/.test(url))).toBe(false)
  await page.getByTestId('mobile-results').getByRole('button', { name: 'Mapa' }).click()
  await expect(page.getByTestId('google-map')).toHaveAttribute('data-map-interaction', 'interactive', { timeout: 20_000 })
  expect(fetched.some((url) => /mobile-map-listings-layer/.test(url))).toBe(true)
})
