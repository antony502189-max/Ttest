import { expect, test } from '@playwright/test'

test.describe('restored home reference controls', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('renders the large rental cards and reference occupant artwork', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    })
    await page.goto('/')

    const modeButtons = page.locator('.m2-mode-switch > button')
    await expect(modeButtons).toHaveCount(2)
    await expect(modeButtons.first()).toBeVisible()
    await expect(modeButtons.last()).toBeVisible()
    await expect(modeButtons.first()).toHaveAccessibleName('HABITACIONES LARGA ESTANCIA')
    await expect(modeButtons.last()).toHaveAccessibleName('HABITACIONES TURÍSTICAS')

    const longStayLabel = modeButtons.first().locator('span').last()
    const tourismLabel = modeButtons.last().locator('span').last()
    await expect(longStayLabel).toHaveAttribute('data-reference-title', 'HABITACIONES')
    await expect(longStayLabel).toHaveAttribute('data-reference-subtitle', 'LARGA ESTANCIA')
    await expect(tourismLabel).toHaveAttribute('data-reference-title', 'HABITACIONES')
    await expect(tourismLabel).toHaveAttribute('data-reference-subtitle', 'TURÍSTICAS')

    const cardHeight = await modeButtons.first().evaluate((element) => element.getBoundingClientRect().height)
    expect(cardHeight).toBeGreaterThanOrEqual(180)

    const longStayTitle = await longStayLabel.evaluate((element) => getComputedStyle(element, '::before').content)
    const longStaySubtitle = await longStayLabel.evaluate((element) => getComputedStyle(element, '::after').content)
    const tourismTitle = await tourismLabel.evaluate((element) => getComputedStyle(element, '::before').content)
    const tourismSubtitle = await tourismLabel.evaluate((element) => getComputedStyle(element, '::after').content)

    expect(longStayTitle).toContain('HABITACIONES')
    expect(longStaySubtitle).toContain('LARGA ESTANCIA')
    expect(tourismTitle).toContain('HABITACIONES')
    expect(tourismSubtitle).toContain('TURÍSTICAS')

    await modeButtons.last().click()
    await expect(modeButtons.last()).toHaveClass(/is-active/)
    await expect.poll(() => modeButtons.last().evaluate((element) => getComputedStyle(element, '::after').content)).toContain('✓')
    await expect.poll(() => modeButtons.last().evaluate((element) => getComputedStyle(element).opacity)).toBe('1')

    const occupantTrigger = page.locator('.m2-occupant-trigger')
    await expect(occupantTrigger).toBeVisible()
    await occupantTrigger.click()

    const options = page.locator('.m2-custom-occupant-list > button[data-m2-occupant-key]')
    await expect(options).toHaveCount(7)
    const referenceIcons = options.locator('img.m2-reference-occupant-icon')
    await expect(referenceIcons).toHaveCount(7)

    for (let index = 0; index < 7; index += 1) {
      await expect(referenceIcons.nth(index)).toHaveAttribute('src', /^blob:/)
      await expect(referenceIcons.nth(index)).toBeVisible()
      await expect.poll(() => referenceIcons.nth(index).evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0)
    }

    const iconBoxes = await referenceIcons.evaluateAll((images) => images.map((image) => {
      const box = image.getBoundingClientRect()
      return { width: Math.round(box.width * 100) / 100, height: Math.round(box.height * 100) / 100 }
    }))
    expect(new Set(iconBoxes.map(({ width }) => width)).size).toBe(1)
    expect(new Set(iconBoxes.map(({ height }) => height)).size).toBe(1)
    expect(iconBoxes[0].width).toBeGreaterThan(50)
    expect(iconBoxes[0].height).toBeGreaterThan(50)

    await options.first().click()
    await expect(options.first()).toHaveClass(/is-selected/)
    await expect.poll(() => referenceIcons.first().evaluate((image) => getComputedStyle(image).borderColor)).toBe('rgb(210, 255, 63)')
  })
})