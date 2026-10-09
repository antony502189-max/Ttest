import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function completeOnboarding(page: import('@playwright/test').Page) {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
}

test('mobile home does not load search results or publication gate modules until needed', async ({ page }) => {
  const modules: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('mobile-search-results-v2') || request.url().includes('mobile-publication-gate')) {
      modules.push(request.url())
    }
  })
  await completeOnboarding(page)
  await page.goto('/#/')
  await expect(page.locator('.m2-home')).toBeVisible()
  expect(modules).toEqual([])

  await page.getByTestId('open-location').focus()
  await expect.poll(() => modules.some((url) => url.includes('mobile-search-results-v2'))).toBe(true)
  expect(modules.some((url) => url.includes('mobile-publication-gate'))).toBe(false)
})

test('mobile list route loads search results', async ({ page }) => {
  const requests: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('mobile-search-results-v2')) requests.push(request.url())
  })
  await completeOnboarding(page)
  await page.goto('/#/buscar?q=Tenerife')
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await expect.poll(() => requests.length).toBeGreaterThan(0)
})

test('mobile map route does not load list search results', async ({ page }) => {
  const requests: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('mobile-search-results-v2')) requests.push(request.url())
  })
  await completeOnboarding(page)
  await page.goto('/#/buscar?q=Tenerife&vista=mapa')
  await expect(page.locator('.m2-map-screen')).toBeVisible()
  expect(requests).toEqual([])
})

test('mobile publication gate loads only for its query route', async ({ page }) => {
  const requests: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('mobile-publication-gate')) requests.push(request.url())
  })
  await completeOnboarding(page)
  await page.goto('/#/')
  await expect(page.locator('.m2-home')).toBeVisible()
  expect(requests).toEqual([])

  await page.goto('/#/?gate=publicar')
  await expect(page.getByTestId('publication-gate')).toBeVisible()
  await expect.poll(() => requests.length).toBeGreaterThan(0)
})
