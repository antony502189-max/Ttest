import { expect, test } from '@playwright/test'

function homeSearchParams(url: string) {
  const hash = new URL(url).hash
  const queryIndex = hash.indexOf('?')
  return new URLSearchParams(queryIndex >= 0 ? hash.slice(queryIndex + 1) : '')
}

test('mobile home restores the PR #154 DOM and ignores removed persisted filters', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:appearance:v1', 'dark')
    localStorage.setItem('112233:listing-access-profile:v1', JSON.stringify({
      occupant: 'any',
      pets: 'Sí',
      smoking: 'No',
    }))
  })

  await page.goto('/#/')
  await expect(page.locator('.m2-home')).toBeVisible()
  await expect(page.locator('.m2-home-extra-filters')).toHaveCount(0)
  await expect(page.locator('[data-mobile-home-extra-filters-host]')).toHaveCount(0)
  await expect(page.getByTestId('mobile-home-pets-yes')).toHaveCount(0)
  await expect(page.getByTestId('mobile-home-smoking-yes')).toHaveCount(0)
  await expect(page.locator('html')).not.toHaveClass(/site-theme-(dark|light)/)
  await expect(page.locator('html')).not.toHaveAttribute('data-appearance')

  await page.getByTestId('open-location').click()
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  const params = homeSearchParams(page.url())
  expect(params.get('mascotas')).toBeNull()
  expect(params.get('fumar')).toBeNull()
  await expect(page.locator('.m2-result-card')).toHaveCount(23)
})
