import { expect, test } from '@playwright/test'

test.describe('mobile menu values never split across lines', () => {
  for (const width of [320, 390, 430]) {
    test(`Russian region and language values are one-line at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 })
      await page.addInitScript(() => {
        localStorage.setItem('112233:mobile-onboarding:v1', 'done')
        localStorage.setItem('112233:language:v1', 'ru')
      })
      await page.goto('/#/menu')
      const menu = page.getByTestId('mobile-menu')
      await expect(menu).toBeVisible()
      const values = menu.locator('.m2-menu-row__trailing b')
      await expect(values).toHaveCount(2)
      await expect(values.nth(0)).toHaveText('España')
      await expect(values.nth(1)).toHaveText('Русский')
      for (const value of await values.all()) {
        const metrics = await value.evaluate((node) => {
          const style = getComputedStyle(node)
          const rect = node.getBoundingClientRect()
          return {
            whiteSpace: style.whiteSpace,
            wordBreak: style.wordBreak,
            height: rect.height,
            maxLineHeight: parseFloat(style.lineHeight),
            clientWidth: node.clientWidth,
            scrollWidth: node.scrollWidth,
          }
        })
        expect(metrics.whiteSpace).toBe('nowrap')
        expect(metrics.wordBreak).toBe('normal')
        expect(metrics.height).toBeLessThanOrEqual(metrics.maxLineHeight + 2)
        expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1)
      }
      const noOverflow = await page.evaluate(() =>
        document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)
      expect(noOverflow).toBe(true)
    })
  }
})

test.describe('admin data loads independently by tab', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.addInitScript(() => {
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      localStorage.setItem('112233:session:v1', JSON.stringify('admin-demo'))
    })
  })

  const user = {
    id: '00000000-0000-4000-8000-000000000041',
    email: 'testing@example.com',
    name: 'Test User',
    role: 'tenant',
    blocked: false,
    phone: '',
    whatsapp: '',
    telegram: '',
    about: '',
    initials: 'TU',
    showPhone: false,
    showWhatsApp: false,
    avatarUrl: null,
    createdAt: '2026-09-01T12:00:00.000Z',
    deletedAt: null,
    lastLoginAt: null,
    listingCount: 0,
    activeRestriction: null,
    isAdmin: false,
  }

  test('users list does not fetch listings, reports, audit or administrators on entry', async ({ page }) => {
    const requests: string[] = []
    await page.route('**/api/v1/admin/**', async (route) => {
      const path = new URL(route.request().url()).pathname
      requests.push(path)
      if (path.endsWith('/admin/users')) {
        await route.fulfill({ status: 200, json: [user] })
        return
      }
      await route.fulfill({ status: 200, json: [] })
    })
    await page.goto('/#/admin')
    await expect(page.locator('.admin-user-list')).toContainText('Test User')
    await expect(page.locator('.admin-detail-loading')).toHaveCount(0)
    expect(requests.some((path) => path.endsWith('/admin/users'))).toBe(true)
    expect(requests.some((path) => path.endsWith('/admin/listings'))).toBe(false)
    expect(requests.some((path) => path.endsWith('/admin/audit-log'))).toBe(false)
    expect(requests.some((path) => path.endsWith('/admin/admins'))).toBe(false)
    await page.locator('.admin-sidebar nav button').filter({ hasText: 'Anuncios' }).click()
    await expect.poll(() => requests.some((path) => path.endsWith('/admin/listings'))).toBe(true)
  })

  test('failed users request ends the spinner and exposes an inline retry', async ({ page }) => {
    let attempts = 0
    await page.route('**/api/v1/admin/users?*', async (route) => {
      attempts += 1
      await route.fulfill(attempts === 1
        ? { status: 503, json: { detail: 'Temporalmente no disponible' } }
        : { status: 200, json: [user] })
    })
    await page.goto('/#/admin')
    const failure = page.locator('.admin-load-error')
    await expect(failure).toBeVisible()
    await expect(failure).toContainText('Temporalmente no disponible')
    await expect(page.locator('.admin-detail-loading')).toHaveCount(0)
    await failure.getByRole('button', { name: 'Reintentar' }).click()
    await expect(page.locator('.admin-user-list')).toContainText('Test User')
    await expect(failure).toHaveCount(0)
    expect(attempts).toBe(2)
  })
})
