import { expect, test, type Page } from '@playwright/test'

async function open(page: Page, route: string, width: number, height: number) {
  await page.setViewportSize({ width, height })
  await page.goto(route)
  await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
}

async function background(page: Page, selector: string) {
  return page.locator(selector).evaluate((element) => getComputedStyle(element).backgroundColor)
}

async function color(page: Page, selector: string) {
  return page.locator(selector).evaluate((element) => getComputedStyle(element).color)
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('desktop home and footer use the customer-requested white presentation', async ({ page }) => {
  await open(page, '/#/', 1440, 900)

  await expect(page.locator('.market-home')).toBeVisible()
  expect(await background(page, '.market-home')).toBe('rgb(255, 255, 255)')
  expect(await background(page, '.home-search-stage')).toBe('rgb(255, 255, 255)')
  expect(await background(page, '.site-footer')).toBe('rgb(255, 255, 255)')

  const heroHeadingColor = await color(page, '.home-hero__content h1')
  expect(heroHeadingColor).not.toBe('rgb(255, 255, 255)')
})

test('mobile home shell uses white surfaces without changing its structure', async ({ page }) => {
  await open(page, '/#/', 390, 844)

  await expect(page.locator('.m2-app')).toBeVisible()
  await expect(page.locator('.m2-screen')).toBeVisible()
  await expect(page.locator('.m2-bottom-nav')).toBeVisible()

  expect(await background(page, '.m2-app')).toBe('rgb(255, 255, 255)')
  expect(await background(page, '.m2-screen')).toBe('rgb(255, 255, 255)')
  expect(await background(page, '.m2-bottom-nav')).toBe('rgba(255, 255, 255, 0.98)')
})

test('mobile search results and filter panels stay light', async ({ page }) => {
  await open(page, '/#/buscar?q=Tenerife', 390, 844)

  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  expect(await background(page, '.m2-results')).toBe('rgb(255, 255, 255)')

  await page.getByRole('button', { name: /Filtros|Filters|Фильтры/i }).click()
  await expect(page.locator('.m2-results-panel')).toBeVisible()
  expect(await background(page, '.m2-results-panel')).toBe('rgba(255, 255, 255, 0.98)')
})
