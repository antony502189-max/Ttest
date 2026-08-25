import { expect, test } from '@playwright/test'

test('notification header badge refreshes immediately after notification state changes', async ({ page }) => {
  let unreadCount = 2
  await page.route('**/api/v1/notifications', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], unreadCount }),
    })
  })

  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()

  const desktopBadge = page.locator('.site-header .notification-count')
  await expect(desktopBadge).toHaveText('2')

  unreadCount = 0
  await page.evaluate(() => window.dispatchEvent(new Event('112233:notifications-updated')))
  await expect(desktopBadge).toHaveCount(0)
})
