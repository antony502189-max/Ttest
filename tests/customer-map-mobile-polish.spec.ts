import { expect, test, type Page } from '@playwright/test'

async function openPublishAsHost(page: Page, language: 'es' | 'en' | 'ru' = 'es') {
  await page.addInitScript(({ language }) => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', language)
    localStorage.removeItem('112233:listing-draft:v3')
    localStorage.removeItem('112233:listing-draft:v2')
  }, { language })
  await page.goto('/#/publicar')
  const continueLabel = language === 'ru' ? 'Продолжить' : language === 'en' ? 'Continue' : 'Continuar'
  await page.getByRole('button', { name: continueLabel }).click()
}

test.describe('customer publish-map polish', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('map is the only visible location control and touch double-tap places the marker', async ({ page }) => {
    await openPublishAsHost(page)

    await expect(page.getByRole('heading', { name: 'Sitúa la habitación' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Centrar de nuevo en la zona', hidden: true })).toBeHidden()
    await expect(page.locator('.approximate-location-selector__grid')).toBeHidden()
    await expect(page.locator('.approximate-location-selector > output')).toBeHidden()
    await expect(page.getByText('Mueve el mapa con el dedo y toca dos veces el lugar deseado para colocar el marcador.')).toBeVisible()

    const map = page.locator('.approximate-location-map')
    await expect(map).toBeVisible()
    await expect(map.locator('.gm-style')).toHaveCount(1)
    await expect(map.locator('.gm-test-pin')).toHaveCount(1)

    const output = page.locator('.approximate-location-selector output')
    const before = await output.textContent()
    const box = await map.boundingBox()
    expect(box).not.toBeNull()
    const clientX = Math.round((box?.x ?? 0) + (box?.width ?? 300) * 0.72)
    const clientY = Math.round((box?.y ?? 0) + (box?.height ?? 240) * 0.38)

    for (let tap = 0; tap < 2; tap += 1) {
      await map.dispatchEvent('pointerdown', { pointerId: tap + 1, pointerType: 'touch', clientX, clientY })
      await map.dispatchEvent('pointerup', { pointerId: tap + 1, pointerType: 'touch', clientX, clientY })
    }

    await expect.poll(async () => output.textContent()).not.toBe(before)
    await expect(map.locator('.gm-test-pin')).toHaveCount(1)
  })

  for (const { language, guidance } of [
    { language: 'en', guidance: 'Move the map with your finger and double-tap the desired place to set the marker.' },
    { language: 'ru', guidance: 'Перемещайте карту пальцем и дважды коснитесь нужного места, чтобы поставить маркер.' },
  ] as const) {
    test(`double-tap guidance follows ${language} locale`, async ({ page }) => {
      await openPublishAsHost(page, language)
      await expect(page.getByText(guidance, { exact: true })).toBeVisible()
      await expect(page.locator('.approximate-location-map')).toHaveAttribute('aria-label', new RegExp(guidance.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
    })
  }
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
