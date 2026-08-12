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
  expect(await page.locator('.m2-bottom-nav button:not(.is-active)').first().evaluate((element) => getComputedStyle(element).color)).toBe('rgb(98, 106, 107)')
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

test('current authentication route stays structured, centered and overflow-free in the light theme', async ({ page }) => {
  for (const [width, height] of [[320, 700], [390, 844], [430, 844], [1024, 900]] as const) {
    await open(page, '/#/acceso', width, height)

    const app = page.locator('.m2-auth-screen')
    const content = page.locator('.m2-auth-content')
    const choice = page.locator('.m2-auth-choice').first()
    await expect(app).toBeVisible()
    await expect(choice).toBeVisible()

    expect(await background(page, '.m2-auth-screen')).toBe('rgb(255, 255, 255)')
    expect(await content.evaluate((element) => getComputedStyle(element).display)).toBe('flex')

    const geometry = await page.evaluate(() => {
      const shell = document.querySelector<HTMLElement>('.m2-auth-screen')!
      const button = document.querySelector<HTMLElement>('.m2-auth-choice')!
      const heading = document.querySelector<HTMLElement>('.m2-auth-content > h1')!
      const shellBox = shell.getBoundingClientRect()
      const buttonBox = button.getBoundingClientRect()
      return {
        viewportWidth: window.innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        shellLeft: shellBox.left,
        shellRight: shellBox.right,
        shellWidth: shellBox.width,
        buttonWidth: buttonBox.width,
        headingSize: Number.parseFloat(getComputedStyle(heading).fontSize),
      }
    })

    expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.viewportWidth)
    expect(geometry.shellWidth).toBeLessThanOrEqual(430.5)
    expect(Math.abs((geometry.shellLeft + geometry.shellRight) / 2 - geometry.viewportWidth / 2)).toBeLessThan(1.5)
    expect(geometry.buttonWidth).toBeGreaterThan(Math.min(geometry.shellWidth - 40, 275))
    expect(geometry.headingSize).toBeLessThanOrEqual(20)
  }
})
