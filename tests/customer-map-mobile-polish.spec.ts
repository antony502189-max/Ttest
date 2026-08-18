import { expect, test, type Page } from '@playwright/test'

async function openPublishAsHost(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
    localStorage.removeItem('112233:listing-draft:v3')
    localStorage.removeItem('112233:listing-draft:v2')
  })
  await page.goto('/#/publicar')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.getByRole('heading', { name: 'Ubicación' })).toBeVisible()
}

test.describe('customer publish-map polish', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('map is the only location control and double click places the marker', async ({ page }) => {
    await openPublishAsHost(page)

    await expect(page.getByRole('button', { name: 'Centrar de nuevo en la zona' })).toHaveCount(0)
    await expect(page.locator('.approximate-location-selector__grid')).toHaveCount(0)
    await expect(page.getByText('Desplaza el mapa y toca dos veces donde quieras colocar el marcador.')).toBeVisible()

    const map = page.locator('.approximate-location-map')
    await expect(map.locator('.gm-style')).toBeVisible()
    await expect(map.locator('.gm-test-pin')).toHaveCount(1)

    const output = page.locator('.approximate-location-selector output')
    const before = await output.textContent()
    const box = await map.boundingBox()
    expect(box).not.toBeNull()

    await map.dblclick({ position: { x: Math.round((box?.width ?? 300) * 0.72), y: Math.round((box?.height ?? 240) * 0.38) } })

    await expect.poll(async () => output.textContent()).not.toBe(before)
    await expect(map.locator('.gm-test-pin')).toHaveCount(1)
  })
})

for (const viewport of [
  { width: 320, height: 700 },
  { width: 360, height: 800 },
  { width: 390, height: 844 },
  { width: 430, height: 932 },
]) {
  test(`home rental cards stay inside their switch at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.addInitScript(() => {
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      localStorage.setItem('112233:language:v1', 'ru')
    })
    await page.goto('/')

    const switcher = page.locator('.m2-mode-switch')
    const buttons = switcher.locator(':scope > button')
    await expect(buttons).toHaveCount(2)
    await buttons.last().click()
    await expect(buttons.last()).toHaveClass(/is-active/)

    const geometry = await switcher.evaluate((element) => {
      const parent = element.getBoundingClientRect()
      const cards = Array.from(element.children).map((child) => {
        const rect = child.getBoundingClientRect()
        return {
          left: rect.left,
          right: rect.right,
          width: rect.width,
          clientWidth: (child as HTMLElement).clientWidth,
          scrollWidth: (child as HTMLElement).scrollWidth,
        }
      })
      return { left: parent.left, right: parent.right, cards }
    })

    for (const card of geometry.cards) {
      expect(card.left).toBeGreaterThanOrEqual(geometry.left - 0.5)
      expect(card.right).toBeLessThanOrEqual(geometry.right + 0.5)
      expect(card.scrollWidth).toBeLessThanOrEqual(card.clientWidth + 1)
    }

    const pageWidth = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth, body: document.body.scrollWidth }))
    expect(pageWidth.document).toBeLessThanOrEqual(pageWidth.viewport)
    expect(pageWidth.body).toBeLessThanOrEqual(pageWidth.viewport)
  })
}
