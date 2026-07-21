import { expect, test, type Page } from '@playwright/test'

const mobileViewport = { width: 390, height: 844 }

async function settleVisuals(page: Page) {
  await page.waitForLoadState('domcontentloaded')
  await page.waitForTimeout(250)
}

test.beforeEach(async ({ page }) => {
  test.setTimeout(60_000)
  await page.setViewportSize(mobileViewport)
})

test('mobile home composition', async ({ page }) => {
  await page.goto('/#/')
  await settleVisuals(page)
  await expect(page).toHaveScreenshot('mobile-home.png', {
    animations: 'disabled',
    mask: [page.locator('.promoted-listing img')],
    maskColor: '#c9c9c9',
    maxDiffPixelRatio: 0.02,
  })
})

test('mobile search results and filters', async ({ page }) => {
  await page.goto('/#/buscar')
  await settleVisuals(page)
  await expect(page).toHaveScreenshot('mobile-search-list.png', {
    animations: 'disabled',
    mask: [page.locator('.property-card__media img')],
    maskColor: '#c9c9c9',
    maxDiffPixelRatio: 0.02,
  })

  await page.getByRole('button', { name: /Todos los filtros/ }).click()
  await expect(page.getByRole('heading', { name: 'Filtros' })).toBeVisible()
  await expect(page).toHaveScreenshot('mobile-filters.png', {
    animations: 'disabled',
    maxDiffPixelRatio: 0.02,
  })
})

test('mobile listing detail', async ({ page }) => {
  await page.goto('/#/habitacion/armeñime-luminosa-01')
  await settleVisuals(page)
  await expect(page).toHaveScreenshot('mobile-listing.png', {
    animations: 'disabled',
    mask: [page.locator('.property-gallery img')],
    maskColor: '#c9c9c9',
    maxDiffPixelRatio: 0.02,
  })
})

test('mobile menu and messages', async ({ page }) => {
  await page.goto('/#/menu')
  await settleVisuals(page)
  await expect(page).toHaveScreenshot('mobile-menu.png', {
    animations: 'disabled',
    maxDiffPixelRatio: 0.02,
  })

  await page.goto('/#/mensajes')
  await expect(page.getByRole('heading', { name: 'Mensajes', exact: true })).toBeVisible()
  await expect(page).toHaveScreenshot('mobile-messages.png', {
    animations: 'disabled',
    maxDiffPixelRatio: 0.02,
  })
})
