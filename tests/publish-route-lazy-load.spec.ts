import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 1366, height: 768 } })

test('publication address enhancements load only when entering a publication route', async ({ page }) => {
  const requests: string[] = []
  const isEnhancerStyleRequest = (url: string) => url.includes('publish-location-enhancer.css') || /publish-route-enhancers-[^/]+\.css/.test(url)
  page.on('request', (request) => requests.push(request.url()))
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))

  await page.goto('/#/')
  await expect(page.getByRole('link', { name: 'Publicar anuncio gratis' })).toBeVisible()
  expect(requests.some((url) => url.includes('publish-route-enhancers'))).toBe(false)
  expect(requests.some(isEnhancerStyleRequest)).toBe(false)

  await page.goto('/#/publicar')
  await expect.poll(() => requests.some((url) => url.includes('publish-route-enhancers'))).toBe(true)
  await expect.poll(() => requests.some(isEnhancerStyleRequest)).toBe(true)
  await expect(page).toHaveURL(/#\/acceso/)
})
