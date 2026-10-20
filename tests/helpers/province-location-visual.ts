import { expect, type Page } from '@playwright/test'

// The pinned PNG contains the retired Tenerife-only banner. Like the existing
// menu redesign gate, enforce geometry/palette until owner baseline approval.
export async function expectProvinceLocationVisual(page: Page) {
  const screen = page.getByTestId('location-screen')
  await expect(screen).toBeVisible()
  await expect(screen.locator('.m2-location-region')).toHaveCount(0)
  const search = screen.getByRole('searchbox')
  await expect(search).toHaveAttribute('placeholder', 'Buscar provincia')
  await expect(screen.locator('.m2-location-action')).toHaveCount(3)
  const geometry = await screen.evaluate(element => {
    const header = element.querySelector('header')!
    const form = element.querySelector('.m2-location-search')!
    const buttons = [...element.querySelectorAll('.m2-location-action')]
    const f = form.getBoundingClientRect()
    return { background: getComputedStyle(element).backgroundColor,
      headerHeight: header.getBoundingClientRect().height,
      search: { x: f.x, width: f.width, height: f.height },
      actions: buttons.map(button => ({ height: button.getBoundingClientRect().height,
        width: button.getBoundingClientRect().width, background: getComputedStyle(button).backgroundColor })),
      overflow: document.documentElement.scrollWidth > innerWidth }
  })
  expect(geometry.background).toBe('rgb(255, 255, 255)')
  expect(geometry.headerHeight).toBeGreaterThanOrEqual(58)
  expect(geometry.headerHeight).toBeLessThanOrEqual(64)
  expect(geometry.search.x).toBe(12)
  expect(geometry.search.width).toBe(366)
  expect(geometry.search.height).toBeGreaterThanOrEqual(56)
  for (const action of geometry.actions) {
    expect(action.width).toBe(366)
    expect(action.height).toBeGreaterThanOrEqual(90)
    expect(action.background).toBe('rgb(255, 255, 255)')
  }
  expect(geometry.overflow).toBe(false)
  await expect(page.getByTestId('province-suggestions')).toHaveCount(0)
  await page.screenshot({ path: 'output/province-location-current.png', animations: 'disabled' })
}
