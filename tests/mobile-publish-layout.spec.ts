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
  const geometry = await page.evaluate(() => {
    const viewport = document.documentElement.clientWidth
    const offenders = Array.from(document.querySelectorAll<HTMLElement>('body *'))
      .map((element) => {
        const rect = element.getBoundingClientRect()
        return {
          tag: element.tagName.toLowerCase(),
          id: element.id,
          className: typeof element.className === 'string' ? element.className : '',
          left: Number(rect.left.toFixed(2)),
          right: Number(rect.right.toFixed(2)),
        }
      })
      .filter((item) => item.left < -1 || item.right > viewport + 1)
      .sort((a, b) => Math.max(b.right - viewport, -b.left) - Math.max(a.right - viewport, -a.left))
      .slice(0, 20)

    return {
      innerWidth: window.innerWidth,
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      bodyClientWidth: document.body.clientWidth,
      bodyScrollWidth: document.body.scrollWidth,
      scrollbarWidth: window.innerWidth - document.documentElement.clientWidth,
      offenders,
    }
  })

  expect(
    geometry.scrollWidth,
    `horizontal overflow: ${JSON.stringify(geometry, null, 2)}`,
  ).toBeLessThanOrEqual(geometry.clientWidth + 1)
  expect(geometry.bodyScrollWidth).toBeLessThanOrEqual(geometry.clientWidth + 1)
}

for (const width of [320, 360, 375, 390, 430]) {
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
