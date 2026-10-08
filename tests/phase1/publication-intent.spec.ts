import { expect, test } from '@playwright/test'
import { fixtures, result, card } from './fixtures'

for (const intent of ['hover', 'focus', 'pointerdown', 'click']) {
  test(`desktop publication ${intent} preserves intentional preload and navigation`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await fixtures(page, (_, route) => route.fulfill({ json: result([card(5)]) }))
    const requested: string[] = []
    page.on('request', request => {
      if (/\/src\/pages\/ListingCreatePage\.tsx/.test(request.url())) requested.push(request.url())
    })
    await page.goto('/')
    const publish = page.locator('.site-header a[href="#/publicar"]')
    await expect(publish).toBeVisible()
    await page.waitForLoadState('networkidle')
    expect(requested).toHaveLength(0)
    if (intent === 'hover') {
      await publish.hover()
      await page.waitForLoadState('networkidle')
      await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
      expect(requested).toHaveLength(0)
    } else {
      if (intent === 'focus') await publish.focus()
      if (intent === 'pointerdown') await publish.dispatchEvent('pointerdown', { pointerType: 'mouse', button: 0 })
      if (intent === 'click') await publish.click()
      await expect.poll(() => requested.length).toBe(1)
      if (intent !== 'click') await publish.click()
      // Anonymous desktop publication intentionally enters the login route.
      await expect(page).toHaveURL(/#\/acceso/)
      await expect(page.getByRole('heading')).not.toHaveCount(0)
    }
  })
}
