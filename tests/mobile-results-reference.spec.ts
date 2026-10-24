import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function openSpanishSearch(page: Page, rentalMode: 'long' | 'holiday' = 'long') {
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
  })
  await page.goto(`/#/buscar?q=Espa%C3%B1a&alquiler=${rentalMode}`)
  const results = page.getByTestId('mobile-results')
  await expect(results).toBeVisible()
  return results
}

test('mobile long-term feed matches the reference hierarchy and uses exactly one visible euro sign', async ({ page }, testInfo) => {
  const results = await openSpanishSearch(page)
  const header = results.locator('.m2-results__header')
  await expect(header.locator('.m2-results__headline-count')).toHaveText(/^[\d.,]+ viviendas$/)
  await expect(header.locator('.m2-results__headline-place')).toHaveText('en España')

  const cap = header.locator('.m2-results__price-cap')
  await expect(cap).toBeVisible()
  await expect(cap.locator('.m2-results__price-cap-copy')).toContainText('SOLO DE HASTA')
  await expect(cap.locator('.m2-results__price-cap-value')).toHaveText('1.000')
  expect(((await cap.textContent()) ?? '').match(/€/g)).toHaveLength(1)
  await expect(cap.locator('.m2-results__price-cap-coin')).toHaveText('€')

  const buttons = results.locator('.m2-results__toolbar button')
  await expect(buttons).toHaveCount(3)
  for (const [index, name] of ['Filtros', 'Orden', 'Mapa'].entries()) {
    await expect(buttons.nth(index)).toHaveText(name)
  }
  await expect(results.locator('.m2-results__summary')).toContainText(/^Viendo \d+ de \d+ viviendas/)
  await expect(results.locator('.m2-results__summary-sort')).toContainText('Relevancia')
  await expect(results.locator('.m2-result-card__media').first()).toBeVisible()

  // Screenshot is attached for review; CI does not silently update visual baselines.
  await testInfo.attach('reference-mobile-results-390.png', {
    body: await results.screenshot(),
    contentType: 'image/png',
  })
  await results.locator('.m2-results__summary-sort').click()
  await expect(results.locator('.m2-results-sort')).toBeVisible()
})

test('reference layout fits 320, 390 and 430 px without header or toolbar collisions', async ({ page }) => {
  const results = await openSpanishSearch(page)
  for (const width of [320, 390, 430]) {
    await page.setViewportSize({ width, height: 844 })
    const positions = await results.evaluate((root) => {
      const box = (selector: string) => root.querySelector(selector)!.getBoundingClientRect()
      const header = box('.m2-results__header')
      const headline = box('.m2-results__headline')
      const cap = box('.m2-results__price-cap')
      const toolbar = box('.m2-results__toolbar')
      const summary = box('.m2-results__summary')
      const buttons = [...root.querySelectorAll('.m2-results__toolbar button')].map((item) => item.getBoundingClientRect())
      return {
        overflow: root.scrollWidth > root.clientWidth,
        headerRight: header.right,
        headlineRight: headline.right,
        capLeft: cap.left,
        capRight: cap.right,
        toolbarTop: toolbar.top,
        headerBottom: header.bottom,
        toolbarBottom: toolbar.bottom,
        summaryTop: summary.top,
        widths: buttons.map((item) => item.width),
      }
    })
    expect(positions.overflow, `horizontal overflow at ${width}px`).toBe(false)
    expect(positions.headlineRight, `headline hits badge at ${width}px`).toBeLessThanOrEqual(positions.capLeft + 1)
    expect(positions.capRight).toBeLessThanOrEqual(positions.headerRight + 1)
    expect(Math.abs(positions.headerBottom - positions.toolbarTop)).toBeLessThanOrEqual(2)
    expect(Math.abs(positions.toolbarBottom - positions.summaryTop)).toBeLessThanOrEqual(2)
    expect(Math.max(...positions.widths) - Math.min(...positions.widths)).toBeLessThanOrEqual(2)
  }
})

test('tourist accommodation never advertises the 1,000 euro monthly limit', async ({ page }) => {
  const results = await openSpanishSearch(page, 'holiday')
  await expect(results.locator('.m2-results__price-cap')).toHaveCount(0)
  await expect(results.locator('.m2-results__headline-place')).toHaveText('en España')
  await expect(results.locator('.m2-results__toolbar button')).toHaveCount(3)
})
