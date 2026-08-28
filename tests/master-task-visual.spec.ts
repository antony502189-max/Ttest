import { expect, test, type Page } from '@playwright/test'

async function open(page: Page, route: string, width: number, height: number) {
  await page.setViewportSize({ width, height })
  await page.goto(route)
  await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
  await page.evaluate(async () => { await document.fonts.ready })
  await page.waitForTimeout(200)
}

async function shot(page: Page, name: string) {
  await expect(page).toHaveScreenshot(`${name}.png`, {
    animations: 'disabled',
    caret: 'hide',
    mask: [page.locator('.gm-style img[role="presentation"], .m2-result-card img, .property-card__media img')],
    maskColor: '#c9c9c9',
    maxDiffPixelRatio: 0.04,
  })
}

async function shotLegacyMobileHome(page: Page, name: string) {
  // Pets/smoking are a deliberate additive control covered by dedicated
  // regressions. Keep the pinned master snapshot focused on the pre-existing
  // shell so unrelated visual drift remains detectable.
  const feedbackControls = page.locator('.m2-home-extra-filters')
  await expect(feedbackControls).toBeVisible()
  const style = await page.addStyleTag({ content: '.m2-home-extra-filters{display:none!important}' })
  try {
    await shot(page, name)
  } finally {
    await style.evaluate((element) => element.remove())
  }
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({ body: document.body.scrollWidth, viewport: window.innerWidth }))
  expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport)
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('master approved home design and responsive matrix', async ({ page }) => {
  test.setTimeout(180_000)
  for (const [width, height] of [[360, 800], [390, 844], [430, 932], [768, 1024], [1024, 900], [1440, 900]] as const) {
    await open(page, '/#/', width, height)
    if (width < 768) await expect(page.locator('.m2-home')).toBeVisible()
    else await expect(page.locator('.home-hero')).toBeVisible()
    await expectNoHorizontalOverflow(page)
    if (width === 390 && height === 844) await shotLegacyMobileHome(page, 'current-home-390x844')
  }
})

test('master current mobile list, map, drawing and location states', async ({ page }) => {
  test.setTimeout(180_000)
  await open(page, '/#/buscar?q=Tenerife', 390, 844)
  await expect(page.getByTestId('mobile-results')).toBeVisible()
  await shot(page, 'current-search-390x844')

  await open(page, '/#/buscar?q=Tenerife&vista=mapa', 390, 844)
  await expect(page.getByTestId('map-search')).toBeVisible()
  await expect(page.locator('.m2-map-toolbar')).toBeVisible()
  await expect(page.locator('.m2-map-canvas')).toBeVisible()
  await shot(page, 'current-map-390x844')

  await open(page, '/#/buscar?q=Tenerife&vista=mapa&dibujar=1', 390, 844)
  await expect(page.getByTestId('map-draw')).toBeVisible()
  await page.getByRole('button', { name: 'Dibujar tu zona' }).click()
  await expect(page.getByTestId('freehand-overlay')).toBeVisible()
  await expectNoHorizontalOverflow(page)

  await open(page, '/#/?panel=ubicacion', 390, 844)
  await expect(page.getByTestId('location-screen')).toBeVisible()
  await expect(page.locator('.m2-location-action')).toHaveCount(3)
  await shot(page, 'current-location-390x844')
})

test('master desktop municipality selection and split map states', async ({ page }) => {
  test.setTimeout(240_000)
  await open(page, '/#/buscar?q=Tenerife', 1024, 844)
  await page.getByRole('button', { name: /Abrir selección de ubicación/i }).first().click()
  await page.getByRole('button', { name: 'Seleccionar zonas en el mapa' }).click()
  const browser = page.getByRole('region', { name: 'Seleccionar zonas de Tenerife' })
  await browser.getByRole('button', { name: /^Adeje\b/ }).click()
  await browser.getByRole('button', { name: /^Arona\b/ }).click()
  await expectNoHorizontalOverflow(page)
  await page.keyboard.press('Escape')

  await open(page, '/#/buscar?q=Tenerife&vista=mapa', 1440, 900)
  await expect(page.locator('.map-results-split')).toBeVisible()
  await expect(page.locator('.results-map__canvas.google-map-canvas')).toHaveAttribute('data-map-instance', 'google-ready', { timeout: 20_000 })
  await expectNoHorizontalOverflow(page)
})
