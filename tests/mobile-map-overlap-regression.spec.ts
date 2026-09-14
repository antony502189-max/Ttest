import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function finishOnboarding(page: Page) {
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
}

test('mobile map does not collapse coincident listings into one marker after zooming', async ({ page }) => {
  await page.goto('/')
  await page.waitForFunction(() => Boolean(localStorage.getItem('112233:listings:v3')))
  const ids = await page.evaluate(() => {
    const key = '112233:listings:v3'
    const payload = JSON.parse(localStorage.getItem(key)!)
    const pair = payload.data.slice(0, 2)
    pair.forEach((listing: any) => {
      listing.coordinates = { lat: 28.1299668, lng: -16.7578612 }
      listing.city = 'Adeje'
      listing.area = 'Arme?ime'
      listing.rentalMode = 'long'
      listing.status = 'Publicado'
    })
    localStorage.setItem(key, JSON.stringify(payload))
    return pair.map((listing: any) => listing.id) as string[]
  })
  await page.reload()
  await finishOnboarding(page)
  await page.locator('.m2-select-row').click()
  await page.getByTestId('search-map').click()
  await expect(page.getByTestId('google-map')).toBeVisible()

  const markers = ids.map((id) => page.getByTestId(`mobile-map-marker-${id}`))
  for (const marker of markers) await expect(marker).toHaveAttribute('data-coincident-count', '2')
  const positions = await Promise.all(markers.map((marker) => marker.getAttribute('data-display-position')))
  expect(new Set(positions).size).toBe(2)
})
