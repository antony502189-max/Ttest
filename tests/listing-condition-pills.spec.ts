import { expect, test } from '@playwright/test'

const listingUrl = '/#/habitacion/arme%C3%B1ime-luminosa-01'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
})

for (const width of [320, 390, 540, 768]) {
  test(`living-condition pills stay rounded, spaced and within their card at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto(listingUrl)

    const section = page.locator('.idealista-listing-page .conditions-block')
    const pills = section.getByTestId('listing-conditions')
    await expect(section.getByRole('heading', { name: 'Normas y convivencia' })).toBeVisible()
    await expect(pills).toBeVisible()
    const chips = pills.locator('.listing-condition-chip')
    expect(await chips.count()).toBeGreaterThanOrEqual(6)

    const layout = await section.evaluate((container) => {
      const list = container.querySelector<HTMLElement>('.listing-conditions')!
      const badges = Array.from(list.querySelectorAll<HTMLElement>('.listing-condition-chip'))
      const card = container.getBoundingClientRect()
      const style = getComputedStyle(list)
      const rectangles = badges.map((badge) => {
        const rect = badge.getBoundingClientRect()
        const computed = getComputedStyle(badge)
        return {
          left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
          width: rect.width, height: rect.height, radius: computed.borderTopLeftRadius,
          whiteSpace: computed.whiteSpace,
        }
      })
      return {
        borderRadius: getComputedStyle(container).borderTopLeftRadius,
        wrap: style.flexWrap,
        gap: parseFloat(style.rowGap),
        left: card.left, right: card.right,
        scrollWidth: container.scrollWidth, clientWidth: container.clientWidth,
        rectangles,
      }
    })

    expect(parseFloat(layout.borderRadius)).toBeGreaterThanOrEqual(10)
    expect(layout.wrap).toBe('wrap')
    expect(layout.gap).toBeGreaterThanOrEqual(8)
    expect(layout.scrollWidth).toBeLessThanOrEqual(layout.clientWidth + 1)

    for (const chip of layout.rectangles) {
      expect(chip.left).toBeGreaterThanOrEqual(layout.left - 1)
      expect(chip.right).toBeLessThanOrEqual(layout.right + 1)
      expect(chip.height).toBeGreaterThanOrEqual(49)
      expect(parseFloat(chip.radius)).toBeGreaterThanOrEqual(24)
      expect(chip.whiteSpace).toBe('normal')
    }
    for (let i = 0; i < layout.rectangles.length; i += 1) {
      for (let j = i + 1; j < layout.rectangles.length; j += 1) {
        const a = layout.rectangles[i], b = layout.rectangles[j]
        const overlapWidth = Math.min(a.right, b.right) - Math.max(a.left, b.left)
        const overlapHeight = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)
        expect(overlapWidth <= 0 || overlapHeight <= 0).toBe(true)
      }
    }
  })
}

test('condition labels have icon and tone parity with the supplied mobile reference', async ({ page }) => {
  await page.setViewportSize({ width: 540, height: 1000 })
  await page.goto(listingUrl)
  const block = page.getByTestId('listing-conditions')
  const chips = block.locator('.listing-condition-chip')
  await expect(chips.first()).toBeVisible()
  await expect(chips.first().locator('svg')).toHaveCount(1)
  await expect(block.getByText('Habitación para 1 persona')).toBeVisible()
  await expect(block.locator('.listing-condition-chip--neutral').first()).toBeVisible()
  await expect(block.locator('.listing-condition-chip--wide')).toHaveCount(2)
  await expect(block.locator('.listing-condition-chip--positive').filter({ hasText: 'Gastos incluidos' })).toBeVisible()
})
