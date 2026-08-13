import { readFileSync } from 'node:fs'
import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function finishOnboarding(page: Page) {
  await page.goto('/')
  if (await page.getByTestId('open-location').isVisible().catch(() => false)) return
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Ahora no' }).click()
  await expect(page.getByTestId('open-location')).toBeVisible()
}

async function assertNoHorizontalOverflow(page: Page) {
  const widths = await page.evaluate(() => ({
    viewport: innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }))
  expect(widths.document).toBeLessThanOrEqual(widths.viewport)
  expect(widths.body).toBeLessThanOrEqual(widths.viewport)
}

test('tourism home card is nudged left without mobile overflow', async ({ page }) => {
  await finishOnboarding(page)
  const tourism = page.locator('.m2-mode-switch > button').nth(1)
  await expect(tourism).toBeVisible()
  await expect(tourism).toHaveCSS('translate', '-4px')
  await assertNoHorizontalOverflow(page)
})

test('filter rental-mode cards reuse the home green and magenta selection language', async ({ page }) => {
  await finishOnboarding(page)
  await page.locator('.m2-mode-switch > button').first().click()
  await page.getByTestId('open-location').click()

  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  await results.getByRole('button', { name: 'Filtros' }).click()

  const vivienda = results.getByRole('button', { name: 'Vivienda', exact: true })
  const turismo = results.getByRole('button', { name: 'Turismo', exact: true })

  await expect(vivienda).toHaveCSS('border-top-color', 'rgb(116, 185, 0)')
  expect(await vivienda.evaluate((node) => getComputedStyle(node).boxShadow)).toContain('rgb(116, 185, 0)')
  expect(await vivienda.evaluate((node) => getComputedStyle(node).backgroundImage)).toContain('rgb(255, 255, 251)')

  await expect(turismo).toHaveCSS('border-top-color', 'rgba(198, 0, 131, 0.34)')
  expect(await turismo.evaluate((node) => getComputedStyle(node).backgroundImage)).toContain('rgb(255, 245, 251)')

  await turismo.click()
  await expect(turismo).toHaveCSS('border-top-color', 'rgb(198, 0, 131)')
  expect(await turismo.evaluate((node) => getComputedStyle(node).boxShadow)).toContain('rgb(198, 0, 131)')
  await assertNoHorizontalOverflow(page)
})

test('publish arrow polish and cascade order stay locked', () => {
  const main = readFileSync('src/main.tsx', 'utf8')
  const css = readFileSync('src/client-mobile-alignment-fixes.css', 'utf8')
  expect(main.indexOf("import './client-mobile-alignment-fixes.css'")).toBeGreaterThan(main.indexOf("import './white-theme-audit-fixes.css'"))
  expect(css).toContain('.publish-page .publish-header > [data-slot="button"]:first-child svg')
  expect(css).toContain('width: 1.5rem;')
  expect(css).toContain('height: 1.5rem;')
  expect(css).toContain('translate: .16rem 0;')
})
