import { expect, test, type Page } from '@playwright/test'

async function openAsHost(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
  })
  await page.reload()
  await page.goto('/#/publicar')
}

async function expectNoHorizontalOverflow(page: Page) {
  const geometry = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    html: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }))
  expect(geometry.html).toBeLessThanOrEqual(geometry.viewport + 1)
  expect(geometry.body).toBeLessThanOrEqual(geometry.viewport + 1)
}

for (const width of [320, 360, 390, 430]) {
  test(`mobile publish header and location controls stay inside ${width}px viewport`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    await openAsHost(page)

    const header = page.locator('.publish-header')
    const exit = header.getByRole('button', { name: 'Salir' })
    await expect(header).toBeVisible()
    await expect(exit).toBeVisible()
    await expect(exit).toHaveCSS('font-size', '0px')

    const exitBox = await exit.boundingBox()
    expect(exitBox).not.toBeNull()
    expect(exitBox!.x).toBeGreaterThanOrEqual(0)
    expect(exitBox!.x + exitBox!.width).toBeLessThanOrEqual(width + 1)
    expect(exitBox!.width).toBeLessThanOrEqual(45)
    await expectNoHorizontalOverflow(page)

    await page.getByRole('button', { name: 'Continuar' }).click()
    const city = page.locator('#publish-city')
    await expect(city).toBeVisible()
    await city.focus()
    await city.selectOption('San Cristóbal de La Laguna')
    await expect(city).toHaveValue('San Cristóbal de La Laguna')

    const cityBox = await city.boundingBox()
    expect(cityBox).not.toBeNull()
    expect(cityBox!.x).toBeGreaterThanOrEqual(0)
    expect(cityBox!.x + cityBox!.width).toBeLessThanOrEqual(width + 1)
    await expectNoHorizontalOverflow(page)
  })
}
