import { expect, test } from '@playwright/test'

const mobileViewports = [
  { width: 360, height: 800 },
  { width: 390, height: 844 },
  { width: 412, height: 915 },
]

for (const viewport of mobileViewports) {
  test(`mobile home rental cards stay aligned after selection at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.addInitScript(() => {
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    })
    await page.goto('/')

    const modeSwitch = page.locator('.m2-mode-switch')
    const modeButtons = modeSwitch.locator(':scope > button')
    const longStay = modeButtons.first()
    const tourism = modeButtons.last()
    const occupantTrigger = page.locator('.m2-occupant-trigger')
    const bottomNav = page.locator('.m2-bottom-nav')

    await expect(modeButtons).toHaveCount(2)
    await expect(longStay).toBeVisible()
    await expect(tourism).toBeVisible()
    await expect(occupantTrigger).toBeVisible()
    await expect(bottomNav).toBeVisible()

    const before = await modeButtons.evaluateAll((buttons) => buttons.map((button) => {
      const box = button.getBoundingClientRect()
      return { x: box.x, y: box.y, width: box.width, height: box.height }
    }))

    expect(Math.abs(before[0].width - before[1].width)).toBeLessThanOrEqual(1)
    expect(Math.abs(before[0].height - before[1].height)).toBeLessThanOrEqual(1)
    expect(before[0].x).toBeGreaterThanOrEqual(0)
    expect(before[1].x + before[1].width).toBeLessThanOrEqual(viewport.width + 1)

    const hasHorizontalOverflowBefore = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    expect(hasHorizontalOverflowBefore).toBe(false)

    await longStay.click()
    await expect(longStay).toHaveClass(/is-active/)
    await expect(tourism).not.toHaveClass(/is-active/)
    await expect.poll(() => longStay.evaluate((element) => getComputedStyle(element, '::after').content)).toContain('✓')

    // The card animates its border for 160ms. Assert the final settled state,
    // not an intermediate interpolated transition color.
    await expect.poll(
      () => longStay.evaluate((element) => getComputedStyle(element).borderColor),
    ).toBe('rgb(116, 185, 0)')

    const after = await modeButtons.evaluateAll((buttons) => buttons.map((button) => {
      const box = button.getBoundingClientRect()
      return { x: box.x, y: box.y, width: box.width, height: box.height }
    }))

    // Selection may lift the active card by a couple of pixels, but it must not
    // resize the cards, shift the grid, or clip the neighbour.
    expect(Math.abs(after[0].width - before[0].width)).toBeLessThanOrEqual(1)
    expect(Math.abs(after[0].height - before[0].height)).toBeLessThanOrEqual(1)
    expect(Math.abs(after[1].x - before[1].x)).toBeLessThanOrEqual(1)
    expect(Math.abs(after[1].width - before[1].width)).toBeLessThanOrEqual(1)
    expect(after[1].x + after[1].width).toBeLessThanOrEqual(viewport.width + 1)

    const textFits = await modeButtons.evaluateAll((buttons) => buttons.every((button) => {
      const label = button.querySelector('span:last-child') as HTMLElement | null
      if (!label) return false
      return label.scrollWidth <= label.clientWidth + 1 && label.scrollHeight <= label.clientHeight + 1
    }))
    expect(textFits).toBe(true)

    const [cardsBox, occupantBox, navBox] = await Promise.all([
      modeSwitch.boundingBox(),
      occupantTrigger.boundingBox(),
      bottomNav.boundingBox(),
    ])
    expect(cardsBox).not.toBeNull()
    expect(occupantBox).not.toBeNull()
    expect(navBox).not.toBeNull()
    expect((cardsBox?.y ?? 0) + (cardsBox?.height ?? 0)).toBeLessThanOrEqual((occupantBox?.y ?? 0) + 1)
    expect((occupantBox?.y ?? 0) + (occupantBox?.height ?? 0)).toBeLessThan(navBox?.y ?? viewport.height)

    const hasHorizontalOverflowAfter = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    expect(hasHorizontalOverflowAfter).toBe(false)
  })
}
