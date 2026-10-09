import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

test('direct mobile search does not initialize the hidden home hero or ads', async ({ page }) => {
  const homeRequests: string[] = []
  const homeImages: string[] = []
  page.on('request', (request) => {
    const url = request.url()
    if (url.includes('/api/v1/listings/homepage-hero') || url.includes('/api/v1/advertisements/homepage')) {
      homeRequests.push(new URL(url).pathname)
    }
    if (url.includes('mobile-hero-') || url.includes('/src/assets/mobile-hero.jpg') || url.includes('fixture-home-ad.svg')) homeImages.push(url)
  })
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.route('**/api/v1/listings/homepage-hero', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: 'null' }))
  await page.route('**/api/v1/advertisements/homepage', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([{
      id: 'fixture-home-ad',
      title: 'Fixture advertisement',
      description: 'Test-only advertisement',
      imageUrl: '/api/v1/advertisements/fixture-home-ad.svg',
      imageWidth: 1200,
      imageHeight: 700,
      destinationType: 'website',
      destinationUrl: 'https://example.test/',
      placement: 'homepage',
    }]),
  }))
  await page.route('**/api/v1/advertisements/fixture-home-ad.svg', (route) => route.fulfill({
    status: 200,
    contentType: 'image/svg+xml',
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="700"><rect width="1200" height="700" fill="#123456"/></svg>',
  }))

  await page.goto('/#/buscar?q=Tenerife')
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await expect(page.locator('.m2-result-card').first()).toBeVisible()
  if (process.env.MOBILE_SEARCH_CAPTURE_PATH) {
    await page.screenshot({ path: process.env.MOBILE_SEARCH_CAPTURE_PATH, animations: 'disabled' })
  }
  expect(homeRequests).toEqual([])
  expect(homeImages).toEqual([])

  await page.getByRole('button', { name: 'Volver' }).click()
  await expect(page.locator('.m2-home')).toBeVisible()
  await expect.poll(() => new Set(homeRequests).size).toBe(2)
  await expect.poll(() => homeImages.some((url) => url.includes('mobile-hero-') || url.includes('/src/assets/mobile-hero.jpg'))).toBe(true)
})
