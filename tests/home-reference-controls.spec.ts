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
    await expect(modeButtons.first()).toHaveAttribute('data-reference-title', 'HABITACIONES')
    await expect(modeButtons.first()).toHaveAttribute('data-reference-subtitle', 'LARGA ESTANCIA')
    await expect(modeButtons.last()).toHaveAttribute('data-reference-title', 'HABITACIONES')
    await expect(modeButtons.last()).toHaveAttribute('data-reference-subtitle', 'TURÍSTICAS')
    await expect(modeButtons.first()).toHaveAccessibleName('Habitaciones, larga estancia')
    await expect(modeButtons.last()).toHaveAccessibleName('Habitaciones turísticas')

    const cardHeight = await modeButtons.first().evaluate((element) => element.getBoundingClientRect().height)
    expect(cardHeight).toBeGreaterThanOrEqual(180)

    const longStayTitle = await modeButtons.first().locator('span').last().evaluate((element) => getComputedStyle(element, '::before').content)
    const longStaySubtitle = await modeButtons.first().locator('span').last().evaluate((element) => getComputedStyle(element, '::after').content)
    const tourismTitle = await modeButtons.last().locator('span').last().evaluate((element) => getComputedStyle(element, '::before').content)
    const tourismSubtitle = await modeButtons.last().locator('span').last().evaluate((element) => getComputedStyle(element, '::after').content)

    expect(longStayTitle).toContain('HABITACIONES')
    expect(longStaySubtitle).toContain('LARGA ESTANCIA')
    expect(tourismTitle).toContain('HABITACIONES')
    expect(tourismSubtitle).toContain('TURÍSTICAS')

    await modeButtons.last().click()
    await expect(modeButtons.last()).toHaveClass(/is-active/)

    const occupantTrigger = page.locator('.m2-occupant-trigger')
    await expect(occupantTrigger).toBeVisible()
    await occupantTrigger.click()

    const options = page.locator('.m2-custom-occupant-list > button[data-m2-occupant-key]')
    await expect(options).toHaveCount(7)
    const referenceIcons = options.locator('img.m2-reference-occupant-icon')
    await expect(referenceIcons).toHaveCount(7)

    for (let index = 0; index < 7; index += 1) {
      await expect(referenceIcons.nth(index)).toHaveAttribute('src', /^data:image\/webp;base64,/)
      await expect(referenceIcons.nth(index)).toBeVisible()
    }
  })
})
