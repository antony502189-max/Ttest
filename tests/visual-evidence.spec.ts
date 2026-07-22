import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const evidence = [
  { name: 'home-375x812', width: 375, height: 812, route: '/#/' },
  { name: 'search-390x844', width: 390, height: 844, route: '/#/buscar?q=Tenerife&alquiler=long' },
  { name: 'map-768x1024', width: 768, height: 1024, route: '/#/buscar?q=Tenerife&alquiler=long&vista=mapa', map: true },
  { name: 'listing-1024x768', width: 1024, height: 768, route: '/#/habitacion/armeñime-luminosa-01' },
  { name: 'publish-1440x900', width: 1440, height: 900, route: '/#/publicar', session: 'host-demo' },
] as const

test('responsive final evidence at the required viewport matrix', async ({ page }) => {
  test.setTimeout(120_000)
  const output = path.join(process.cwd(), 'output', 'playwright', 'responsive', 'final')
  await mkdir(output, { recursive: true })
  for (const item of evidence) {
    await page.setViewportSize({ width: item.width, height: item.height })
    await page.goto('/#/')
    await page.evaluate((session) => localStorage.setItem('112233:session:v1', JSON.stringify(session ?? null)), 'session' in item ? item.session : null)
    await page.reload()
    await page.goto(item.route)
    await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
    if ('map' in item && item.map) await page.locator('.google-map-canvas').waitFor({ state: 'visible' })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBeTruthy()
    await page.screenshot({ path: path.join(output, `${item.name}.png`), animations: 'disabled' })
  }
})
