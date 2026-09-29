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

test('desktop navigation preloads the next route on link intent', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.route(/\/src\/pages\/FavoritesPage\.tsx(?:\?.*)?$/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 450))
    await route.continue()
  })
  await page.goto('/#/')
  await expect(page.getByRole('heading', { name: 'Solo habitaciones' })).toBeVisible()
  const favorites = page.getByRole('link', { name: 'Favoritos' }).first()
  const moduleLoaded = page.waitForResponse((response) => /\/src\/pages\/FavoritesPage\.tsx/.test(response.url()))
  await favorites.hover()
  await moduleLoaded

  await page.evaluate(() => {
    (window as typeof window & { routeLoaderSeen?: boolean }).routeLoaderSeen = false
    new MutationObserver(() => {
      if (document.querySelector('.route-transition-loading')) {
        (window as typeof window & { routeLoaderSeen?: boolean }).routeLoaderSeen = true
      }
    }).observe(document.body, { childList: true, subtree: true })
  })
  await favorites.click()
  await expect(page.locator('.favorites-page')).toBeVisible()
  expect(await page.evaluate(() => (window as typeof window & { routeLoaderSeen?: boolean }).routeLoaderSeen)).toBe(false)
})

test('publication helpers stay out of Home and load on publish intent', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  const requests: string[] = []
  page.on('request', (request) => requests.push(request.url()))
  await page.goto('/#/')
  await expect(page.getByRole('heading', { name: 'Solo habitaciones' })).toBeVisible()
  expect(requests.some((url) => /publish-(?:location-enhancer|address-lifecycle)\.tsx/.test(url))).toBe(false)
  await page.getByRole('link', { name: 'Publicar anuncio gratis' }).hover()
  await expect.poll(() => requests.filter((url) => /publish-(?:location-enhancer|address-lifecycle)\.tsx/.test(url)).length).toBe(2)
})
