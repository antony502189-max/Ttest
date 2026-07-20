import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

for (const route of ['/#/', '/#/buscar?q=Tenerife', '/#/habitacion/armeñime-luminosa-01', '/#/acceso']) {
  test(`axe sin impactos serious/critical: ${route}`, async ({ page }) => {
    await page.goto(route)
    await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
    const results = await new AxeBuilder({ page }).exclude('.leaflet-map-canvas').analyze()
    expect(results.violations.filter((item) => item.impact === 'serious' || item.impact === 'critical')).toEqual([])
  })
}
