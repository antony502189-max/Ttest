import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'
import { isExpectedHeadlessVectorFallback } from './helpers/google-maps-console'

const matrix = [
  { width: 375, height: 812, mode: 'mobile' },
  { width: 390, height: 844, mode: 'mobile' },
  { width: 768, height: 1024, mode: 'tablet' },
  { width: 1024, height: 768, mode: 'desktop' },
  { width: 1440, height: 900, mode: 'desktop' },
] as const

async function openMap(page: Page, width: number, height: number) {
  await page.setViewportSize({ width, height })
  await page.goto('/#/buscar?q=Tenerife&vista=mapa')
  await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
  await page.evaluate(async () => { await document.fonts.ready })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('results map keeps the current mobile shell and desktop split geometry across the responsive matrix', async ({ page }) => {
  test.setTimeout(240_000)
  const unexpectedConsoleErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() !== 'error' || isExpectedHeadlessVectorFallback(message.text())) return
    unexpectedConsoleErrors.push(message.text())
  })

  const output = path.join(process.cwd(), 'output', 'playwright', 'idealista-parity')
  await mkdir(output, { recursive: true })

  for (const viewport of matrix) {
    await openMap(page, viewport.width, viewport.height)
    const mapSelector = viewport.mode === 'mobile' ? '.m2-map-canvas' : '.google-map-canvas'
    await expect(page.locator(mapSelector)).toBeVisible({ timeout: 20_000 })
    if (viewport.mode !== 'mobile') {
      await expect(page.locator(mapSelector)).toHaveAttribute('data-map-instance', 'google-ready', { timeout: 20_000 })
    }

    const geometry = await page.locator(mapSelector).evaluate((node) => {
      const box = node.getBoundingClientRect()
      return {
        documentWidth: document.documentElement.scrollWidth,
        viewportWidth: document.documentElement.clientWidth,
        mapWidth: box.width,
        mapHeight: box.height,
        mapBottom: box.bottom,
        viewportHeight: window.innerHeight,
      }
    })

    expect(geometry.documentWidth, `${viewport.width}px horizontal overflow`).toBeLessThanOrEqual(geometry.viewportWidth + 1)
    expect(geometry.mapWidth).toBeGreaterThan(viewport.mode === 'mobile' ? viewport.width - 2 : 360)
    expect(geometry.mapHeight).toBeGreaterThan(viewport.mode === 'mobile' ? 500 : 360)

    if (viewport.mode === 'mobile') {
      await expect(page.getByTestId('map-search')).toBeVisible()
      await expect(page.locator('.m2-map-toolbar')).toBeVisible()
      await expect(page.locator('.m2-map-controls')).toBeVisible()
      await expect(page.locator('.m2-bottom-nav')).toHaveCount(0)
    } else {
      await expect(page.locator('.map-results-split')).toBeVisible()
      await expect(page.locator('.idealista-results-layout.is-map-view > .filter-sidebar')).toBeHidden()
      expect(geometry.mapBottom).toBeLessThanOrEqual(geometry.viewportHeight + 12)
    }

    await page.screenshot({
      path: path.join(output, `final-map-${viewport.width}x${viewport.height}.png`),
      animations: 'disabled',
      caret: 'hide',
    })
  }

  expect(unexpectedConsoleErrors).toEqual([])
})
