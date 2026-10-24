import { expect, type Page } from '@playwright/test'

/**
 * The owner approved a new mobile-results reference. Its previous
 * current-search-390x844 PNG remains in the protected baseline branch,
 * but is superseded for this surface only. Check layout invariants here
 * until an owner-reviewed visual-baseline update is explicitly run.
 */
export async function expectReferenceMobileResults(page: Page) {
  const results = page.getByTestId('mobile-results')
  const header = results.locator('.m2-results__header')
  await expect(results).toBeVisible()
  await expect(header.locator('.m2-results__headline strong')).toHaveText(/^[\d.,]+ viviendas$/)
  await expect(header.locator('.m2-results__headline span')).toHaveText(/^en /)
  const cap = header.locator('.m2-results__price-cap')
  await expect(cap).toBeVisible()
  await expect(cap.locator('.m2-results__price-cap-label')).toHaveText('SOLO DE HASTA')
  await expect(cap.locator('.m2-results__price-cap-value')).toHaveText('1.000')
  expect((await cap.textContent())?.match(/€/g)).toHaveLength(1)
  await expect(results.locator('.m2-results__toolbar button')).toHaveCount(3)
  await expect(results.locator('.m2-results__summary-sort')).toContainText('Relevancia')

  const layout = await results.evaluate((root) => {
    const rect = (selector: string) => root.querySelector(selector)!.getBoundingClientRect()
    const header = rect('.m2-results__header')
    const title = rect('.m2-results__headline')
    const badge = rect('.m2-results__price-cap')
    const toolbar = rect('.m2-results__toolbar')
    const summary = rect('.m2-results__summary')
    const widths = [...root.querySelectorAll('.m2-results__toolbar button')]
      .map((item) => item.getBoundingClientRect().width)
    return {
      background: getComputedStyle(root.querySelector('.m2-results__header')!).backgroundColor,
      countWeight: Number(getComputedStyle(root.querySelector('.m2-results__headline strong')!).fontWeight),
      titleRight: title.right,
      badgeLeft: badge.left,
      badgeRight: badge.right,
      headerRight: header.right,
      headerBottom: header.bottom,
      toolbarTop: toolbar.top,
      toolbarBottom: toolbar.bottom,
      summaryTop: summary.top,
      toolbarWidths: widths,
      noHorizontalOverflow: root.scrollWidth <= root.clientWidth,
    }
  })

  expect(layout.background).toBe('rgb(255, 255, 255)')
  expect(layout.countWeight).toBeGreaterThanOrEqual(800)
  expect(layout.titleRight).toBeLessThanOrEqual(layout.badgeLeft + 1)
  expect(layout.badgeRight).toBeLessThanOrEqual(layout.headerRight + 1)
  expect(Math.abs(layout.toolbarTop - layout.headerBottom)).toBeLessThanOrEqual(2)
  expect(Math.abs(layout.summaryTop - layout.toolbarBottom)).toBeLessThanOrEqual(2)
  expect(Math.max(...layout.toolbarWidths) - Math.min(...layout.toolbarWidths)).toBeLessThanOrEqual(2)
  expect(layout.noHorizontalOverflow).toBe(true)
}
