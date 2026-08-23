import { expect, test } from '@playwright/test'

const mobileViewports = [
  { width: 343, height: 800 },
  { width: 360, height: 800 },
  { width: 390, height: 844 },
  { width: 412, height: 915 },
]

for (const viewport of mobileViewports) {
  test(`mobile home rental cards stay equal, outlined and inside viewport at ${viewport.width}x${viewport.height}`, async ({ page }) => {
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

    const readBoxes = () => modeButtons.evaluateAll((buttons) => buttons.map((button) => {
      const box = button.getBoundingClientRect()
      return { x: box.x, y: box.y, width: box.width, height: box.height, right: box.right }
    }))

    const expectCompleteBorders = async () => {
      const borders = await modeButtons.evaluateAll((buttons) => buttons.map((button) => {
        const style = getComputedStyle(button)
        return {
          topWidth: style.borderTopWidth,
          rightWidth: style.borderRightWidth,
          bottomWidth: style.borderBottomWidth,
          leftWidth: style.borderLeftWidth,
          topStyle: style.borderTopStyle,
          rightStyle: style.borderRightStyle,
          bottomStyle: style.borderBottomStyle,
          leftStyle: style.borderLeftStyle,
        }
      }))

      for (const border of borders) {
        expect(border.topWidth).toBe('2px')
        expect(border.rightWidth).toBe('2px')
        expect(border.bottomWidth).toBe('2px')
        expect(border.leftWidth).toBe('2px')
        expect(border.topStyle).toBe('solid')
        expect(border.rightStyle).toBe('solid')
        expect(border.bottomStyle).toBe('solid')
        expect(border.leftStyle).toBe('solid')
      }
    }

    const before = await readBoxes()

    expect(Math.abs(before[0].height - before[1].height)).toBeLessThanOrEqual(1)
    expect(Math.abs(before[0].width - before[1].width)).toBeLessThanOrEqual(1)
    expect(before[0].x).toBeGreaterThanOrEqual(10)
    expect(before[1].right).toBeLessThanOrEqual(viewport.width - 10)
    await expectCompleteBorders()

    const hasHorizontalOverflowBefore = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    expect(hasHorizontalOverflowBefore).toBe(false)

    await longStay.click()
    await expect(longStay).toHaveClass(/is-active/)
    await expect(tourism).not.toHaveClass(/is-active/)
    await expect.poll(() => longStay.evaluate((element) => getComputedStyle(element, '::after').content)).toContain('✓')
    await expect.poll(() => longStay.evaluate((element) => getComputedStyle(element).borderColor)).toBe('rgb(116, 185, 0)')

    const afterLongStay = await readBoxes()
    expect(Math.abs(afterLongStay[0].width - before[0].width)).toBeLessThanOrEqual(1)
    expect(Math.abs(afterLongStay[0].height - before[0].height)).toBeLessThanOrEqual(1)
    expect(Math.abs(afterLongStay[1].x - before[1].x)).toBeLessThanOrEqual(1)
    expect(Math.abs(afterLongStay[1].width - before[1].width)).toBeLessThanOrEqual(1)
    expect(Math.abs(afterLongStay[0].width - afterLongStay[1].width)).toBeLessThanOrEqual(1)
    expect(afterLongStay[0].x).toBeGreaterThanOrEqual(10)
    expect(afterLongStay[1].right).toBeLessThanOrEqual(viewport.width - 10)
    await expectCompleteBorders()

    await tourism.click()
    await expect(tourism).toHaveClass(/is-active/)
    await expect(longStay).not.toHaveClass(/is-active/)
    await expect.poll(() => tourism.evaluate((element) => getComputedStyle(element, '::after').content)).toContain('✓')
    await expect.poll(() => tourism.evaluate((element) => getComputedStyle(element).borderColor)).toBe('rgb(198, 0, 131)')

    const afterTourism = await readBoxes()
    expect(Math.abs(afterTourism[0].width - afterTourism[1].width)).toBeLessThanOrEqual(1)
    expect(Math.abs(afterTourism[0].height - afterTourism[1].height)).toBeLessThanOrEqual(1)
    expect(afterTourism[0].x).toBeGreaterThanOrEqual(10)
    expect(afterTourism[1].right).toBeLessThanOrEqual(viewport.width - 10)
    await expectCompleteBorders()

    const textFits = await modeButtons.evaluateAll((buttons) => buttons.every((button) => {
      const label = button.querySelector('span:last-child') as HTMLElement | null
      if (!label) return false
      return label.scrollWidth <= label.clientWidth + 1 && label.scrollHeight <= label.clientHeight + 1
    }))
    expect(textFits).toBe(true)

    const titlesStayOnOneLine = await modeButtons.evaluateAll((buttons) => buttons.every((button) => {
      const label = button.querySelector('span:last-child') as HTMLElement | null
      if (!label) return false
      return getComputedStyle(label, '::before').whiteSpace === 'nowrap'
    }))
    expect(titlesStayOnOneLine).toBe(true)

    const [cardsBox, occupantBox, navBox] = await Promise.all([
      modeSwitch.boundingBox(),
      occupantTrigger.boundingBox(),
      bottomNav.boundingBox(),
    ])
    expect(cardsBox).not.toBeNull()
    expect(occupantBox).not.toBeNull()
    expect(navBox).not.toBeNull()
    expect((cardsBox?.x ?? 0)).toBeGreaterThanOrEqual(10)
    expect((cardsBox?.x ?? 0) + (cardsBox?.width ?? 0)).toBeLessThanOrEqual(viewport.width - 10)
    expect((cardsBox?.y ?? 0) + (cardsBox?.height ?? 0)).toBeLessThanOrEqual((occupantBox?.y ?? 0) + 1)
    expect((occupantBox?.y ?? 0) + (occupantBox?.height ?? 0)).toBeLessThan(navBox?.y ?? viewport.height)

    const hasHorizontalOverflowAfter = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    expect(hasHorizontalOverflowAfter).toBe(false)
  })
}
