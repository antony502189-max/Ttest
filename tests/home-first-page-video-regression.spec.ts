import { expect, test } from '@playwright/test'

const mobileViewports = [
  { width: 343, height: 800 },
  { width: 360, height: 800 },
  { width: 390, height: 844 },
  { width: 412, height: 915 },
]

for (const viewport of mobileViewports) {
  test(`single residential card stays outlined and inside the viewport at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
    await page.goto('/')

    const switcher = page.locator('.m2-mode-switch')
    const modes = switcher.locator(':scope > button')
    const longStay = modes.first()
    const occupant = page.locator('.m2-occupant-trigger')
    const navigation = page.locator('.m2-bottom-nav')

    await expect(modes).toHaveCount(1)
    await expect(longStay).toBeVisible()
    await expect(longStay).toHaveClass(/is-active/)
    await expect(page.getByRole('button', { name: /Turismo/ })).toHaveCount(0)
    await expect(occupant).toBeVisible()
    await expect(navigation).toBeVisible()

    const before = await longStay.boundingBox()
    expect(before).not.toBeNull()
    expect(before!.x).toBeGreaterThanOrEqual(10)
    expect(before!.x + before!.width).toBeLessThanOrEqual(viewport.width - 10)

    const border = await longStay.evaluate((element) => {
      const style = getComputedStyle(element)
      return {
        widths: [style.borderTopWidth, style.borderRightWidth, style.borderBottomWidth, style.borderLeftWidth],
        styles: [style.borderTopStyle, style.borderRightStyle, style.borderBottomStyle, style.borderLeftStyle],
        color: style.borderColor,
        selected: getComputedStyle(element, '::after').content,
      }
    })
    expect(border.widths).toEqual(['2px', '2px', '2px', '2px'])
    expect(border.styles).toEqual(['solid', 'solid', 'solid', 'solid'])
    expect(border.color).toBe('rgb(116, 185, 0)')
    expect(border.selected).toContain('✓')

    await longStay.click()
    const after = await longStay.boundingBox()
    expect(after).not.toBeNull()
    expect(Math.abs(after!.width - before!.width)).toBeLessThanOrEqual(1)
    expect(Math.abs(after!.height - before!.height)).toBeLessThanOrEqual(1)

    const labelFits = await longStay.evaluate((button) => {
      const label = button.querySelector('span:last-child') as HTMLElement | null
      return Boolean(label && label.scrollWidth <= label.clientWidth + 1
        && label.scrollHeight <= label.clientHeight + 1
        && getComputedStyle(label, '::before').whiteSpace === 'nowrap')
    })
    expect(labelFits).toBe(true)

    const [switcherBox, occupantBox, navBox] = await Promise.all([
      switcher.boundingBox(), occupant.boundingBox(), navigation.boundingBox(),
    ])
    expect(switcherBox).not.toBeNull()
    expect(occupantBox).not.toBeNull()
    expect(navBox).not.toBeNull()
    expect(switcherBox!.x).toBeGreaterThanOrEqual(10)
    expect(switcherBox!.x + switcherBox!.width).toBeLessThanOrEqual(viewport.width - 10)
    expect(switcherBox!.y + switcherBox!.height).toBeLessThanOrEqual(occupantBox!.y + 1)
    expect(occupantBox!.y + occupantBox!.height).toBeLessThan(navBox!.y)

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
    expect(overflow).toBe(false)
  })
}
